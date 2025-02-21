import os
import json
from flask import Flask, redirect, request, send_from_directory, render_template, url_for, session
from google.cloud import storage
import google.generativeai as genai
import requests
import pyrebase

app = Flask(__name__)
app.secret_key = 'saipranaygcpassignment2'

bucket_name = 'gcpassignment2-csbucket'
storage_client = storage.Client()
os.makedirs('files', exist_ok=True)

firebaseConfig = {
    "apiKey": "AIzaSyBxoqEroPT5ZQGtQ9xhkP-B8eCmMrj7tk8",
    "authDomain": "gcpassignment-f605d.firebaseapp.com",
    "databaseURL": "https://gcpassignment-f605d-default-rtdb.firebaseio.com",
    "projectId": "gcpassignment-f605d",
    "storageBucket": "https://console.cloud.google.com/storage/browser/gcpassignment2-csbucket"
}

firebase = pyrebase.initialize_app(firebaseConfig)
auth = firebase.auth()
genai.configure(api_key='AIzaSyABY4oVvH7JrxpA70rv0vhlWLJ5WjAVjoI')

def upload_to_gemini(path, mime_type=None):
    file = genai.upload_file(path, mime_type=mime_type)
    print(f"Uploaded file '{file.display_name}' as: {file.uri}")
    return file

def generative_ai(image_file):
    generation_config = {
        "temperature": 1,
        "top_p": 0.95,
        "top_k": 64,
        "max_output_tokens": 8192,
        "response_mime_type": "text/plain",
    }
    model = genai.GenerativeModel(model_name="gemini-1.5-flash", generation_config=generation_config)
    files = upload_to_gemini(image_file, mime_type="image/jpeg")

    chat_session = model.start_chat(
        history=[{"role": "user", "parts": [files, "generate title and description for the image and return the response in json format"]}]
    )
    
    response = chat_session.send_message("INSERT_INPUT_HERE")
    return response.text

def upload1(bucket_name, sources, destination, user_id):
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(f"{user_id}/{destination}")
    blob.upload_from_file(sources)

def download(bucket_name, source, destination):
    bucket = storage_client.bucket(bucket_name)
    os.makedirs(os.path.dirname(destination), exist_ok=True)
    blob = bucket.blob(source)
    blob.download_to_filename(destination)

def list_files(bucket_name, user_id):
    bucket = storage_client.bucket(bucket_name)
    blobs = bucket.list_blobs(prefix=f"{user_id}/")
    return [i.name for i in blobs]

@app.route('/')
def index():
    user_id = session.get('user')
    if not user_id:
        return redirect('/login')
    
    folder = os.path.join('files', user_id)
    os.makedirs(folder, exist_ok=True)

    names = list_files(bucket_name, user_id)

    for name in names:
        path = os.path.join(folder, name.split('/')[-1])
        if not os.path.exists(path):
            download(bucket_name, name, path)

    files_list = {}
    for name in names:
        if name.lower().endswith(('.jpg', '.jpeg', '.png')):
            texts = os.path.splitext(name)[0] + '.txt'
            description = None
            if os.path.exists(os.path.join(folder, texts)):
                with open(os.path.join(folder, texts), 'r') as txts:
                    description = txts.read()
            if os.path.exists(os.path.join(folder, os.path.basename(name))):
                files_list[os.path.basename(name)] = description

    return render_template('index.html', images=files_list, user_id=user_id)

@app.route('/upload', methods=['POST'])
def upload():
    if 'user' not in session:
        return redirect('/login')

    user_id = session['user']
    folder = os.path.join('files', user_id)
    os.makedirs(folder, exist_ok=True)

    file = request.files['image']
    filename = file.filename
    path = os.path.join(folder, filename)
    file.save(path)

    response = generative_ai(path)

    try:
        response = response.replace('json', '').replace('```', '').strip()
        response = json.loads(response)
        title = response.get('title', 'No title present')
        description = response.get('description', 'No description present')
    except:
        return "No response received"

    path1 = os.path.join(folder, os.path.splitext(filename)[0] + '.txt')
    with open(path1, 'w') as p:
        p.write(f"{title}\n{description}")

    with open(path1, 'rb') as p:
        upload1(bucket_name, p, os.path.basename(path1), user_id)

    file.seek(0)
    upload1(bucket_name, file, os.path.basename(path), user_id)

    return redirect('/')

@app.route('/files/<user_id>/<filename>')
def getfiles(filename, user_id):
    return send_from_directory(os.path.join('files', user_id), filename)

@app.route('/view/<user_id>/<filename>')
def view_file(user_id, filename):
    text_file = os.path.splitext(filename)[0] + '.txt'
    title = "No title"
    description = "No description"
    path = os.path.join('./files', user_id, text_file)

    if os.path.exists(path):
        with open(path, 'r') as o:
            content = o.read()
            lines = content.split('\n')
            title = lines[0].strip() if lines else "No title"
            description = '\n'.join(lines[1:]).strip() if len(lines) > 1 else "No description"

    return render_template('view.html', filename=filename, title=title, description=description, user_id=user_id)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        try:
            user = auth.create_user_with_email_and_password(email, password)
            session['user'] = user['localId']
            return redirect('/')
        except Exception:
            return "Error: Unable to sign up"
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        try:
            user = auth.sign_in_with_email_and_password(email, password)
            session['user'] = user['localId']
            return redirect('/')
        except:
            return "Invalid credentials"
    return render_template('login.html')

@app.route('/logout', methods=['GET', 'POST'])
def logout():
    session.pop('user', None)
    return redirect('/login')

if __name__ == '__main__':
    app.run(port=8080, debug=True)
