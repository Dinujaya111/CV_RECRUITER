from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
import os
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize, sent_tokenize
from nltk.stem import PorterStemmer
from flask import render_template_string
import subprocess
import PyPDF2

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# MySQL Configuration
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'cv_recruiter'
mysql = MySQL(app)

# Function to create MySQL connection
def create_mysql_connection():
    return mysql.connection.cursor()

# Upload folder
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Create uploads folder if it doesn't exist
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Download NLTK data
nltk.download('stopwords')
nltk.download('punkt')

# Function to tokenize text and remove stopwords
def tokenize_and_remove_stopwords(text):
    stop_words = set(stopwords.words('english'))
    tokens = word_tokenize(text.lower())
    filtered_tokens = [word for word in tokens if word not in stop_words]
    return filtered_tokens

# Function to extract skills from CV text
def extract_skills(text):
    # Load a list of common skills
    with open('static/skills.txt', 'r') as f:
        skill_list = [line.strip().lower() for line in f]

    tokens = tokenize_and_remove_stopwords(text)
    skills = [token for token in tokens if token in skill_list]
    return list(set(skills))

# Function to extract education details from CV text
def extract_education(text):
    education = []
    sentences = sent_tokenize(text)
    for sentence in sentences:
        if any(phrase.lower() in sentence.lower() for phrase in ['bachelor', 'master', 'university', 'college']):
            education.append(sentence)
    return education

# Function to extract experience details from CV text
def extract_experience(text):
    experience = []
    sentences = sent_tokenize(text)
    for sentence in sentences:
        if any(phrase.lower() in sentence.lower() for phrase in ['experience', 'worked', 'employment']):
            experience.append(sentence)
    return experience



@app.route('/')
def index():
    return render_template('index.html')

@app.route('/dashboard')
def dashboard():
    if 'loggedin' in session:
        return render_template('upload.html')
    else:
        flash('You need to login first!', 'error')
        return redirect(url_for('login'))

# Add the file upload endpoint
@app.route('/upload', methods=['POST'])
def upload_file():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file part', 'error')
            return redirect(request.url)

        file = request.files['file']

        if file.filename == '':
            flash('No selected file', 'error')
            return redirect(request.url)

        if file:
            filename = file.filename
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)

            # Save filename to session
            session['filename'] = filename

            # Save metadata to database
            cursor = create_mysql_connection()
            cursor.execute("INSERT INTO cv_files (user_id, file_name) VALUES (%s, %s)", (session['user_id'], filename))
            mysql.connection.commit()
            cursor.close()

            flash('File uploaded successfully', 'success')
            return redirect(url_for('cv_view'))

    return redirect(url_for('dashboard'))


# Admin credentials
ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD = '12345'

# Admin dashboard route
@app.route('/admin_dashboard')
def admin_dashboard():
    if 'loggedin' in session and session['username'] == ADMIN_USERNAME:
        return render_template('admin_dashboard.html')
    else:
        flash('You need to login as an admin!', 'error')
        return redirect(url_for('login'))



#add the login_details
@app.route('/login_details')
def login_details():
    if 'loggedin' in session and session['username'] == ADMIN_USERNAME:
        cursor = create_mysql_connection()
        if cursor:
            try:
                cursor.execute("SELECT user_id, username, email FROM users")
                users = [{'user_id': row[0], 'username': row[1], 'email': row[2]} for row in cursor.fetchall()]
                print(users)  # Add this line to print the fetched data
                cursor.close()
                return render_template('login_details.html', users=users)
            except Exception as e:
                print(f"Error fetching user data: {e}")  # Add this line to print any error
                cursor.close()
                flash('Error fetching user data.', 'error')
                return redirect(url_for('login'))
        else:
            flash('Error connecting to the database.', 'error')
            return redirect(url_for('login'))
    else:
        flash('You need to login as an admin!', 'error')
        return redirect(url_for('login'))


@app.route('/cv_info')
def cv_info():
    if 'loggedin' in session:
        # Get filename from session
        filename = session.get('filename')

        # Check if filename is None
        if filename is None:
            flash('No file uploaded', 'error')
            return redirect(url_for('dashboard'))

        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

        # Save metadata to database
        cursor = create_mysql_connection()
        cursor.execute("INSERT INTO cv_files (user_id, file_name) VALUES (%s, %s)", (session['user_id'], filename))
        mysql.connection.commit()
        cv_file_id = cursor.lastrowid

        # Perform CV analysis using PyPDF2
        pdf_file = open(file_path, 'rb')
        pdf_reader = PyPDF2.PdfReader(pdf_file)

        text_content = ''
        for page_num in range(len(pdf_reader.pages)):
            page = pdf_reader.pages[page_num]
            text_content += page.extract_text()

        # Close the PDF file
        pdf_file.close()

        skills = extract_skills(text_content)
        education = extract_education(text_content)
        experience = extract_experience(text_content)

        # Save skills to the cv_skills table
        for skill in skills:
            cursor.execute("INSERT INTO cv_skills (cv_file_id, skill) VALUES (%s, %s)", (cv_file_id, skill))

        # Save education to the cv_education table
        for sentence in education:
            cursor.execute("INSERT INTO cv_education (cv_file_id, sentence) VALUES (%s, %s)", (cv_file_id, sentence))

        # Save experience to the cv_experience table
        for sentence in experience:
            cursor.execute("INSERT INTO cv_experience (cv_file_id, sentence) VALUES (%s, %s)", (cv_file_id, sentence))

        mysql.connection.commit()

        # Close the cursor
        cursor.close()

        # Pass the analysis results to a template for display
        return render_template('cv_info.html', skills=skills, education=education, experience=experience)

    return redirect(url_for('dashboard'))



@app.route('/online_interview')
def online_interview():
    if 'loggedin' in session:
        return render_template('online_interview.html')
    else:
        flash('You need to login first!', 'error')
        return redirect(url_for('login'))


# Add the enumerate function to the Jinja2 environment
app.jinja_env.globals['enumerate'] = enumerate



# Now you can render the template
#return render_template_string('leaderboard.html', user_scores=user_scores, skill_counts=skill_counts)
@app.route('/leaderboard')
def leaderboard():
    if 'loggedin' in session:
        cursor = create_mysql_connection()

        # Query to get the quiz results for all users
        cursor.execute("SELECT u.user_id, u.username, q.q1_answer, q.q2_answer, q.q3_answer, q.q4_answer, q.q5_answer, q.q6_answer, q.q7_answer, q.q8_answer, q.q9_answer, q.q10_answer FROM quiz q JOIN users u ON q.user_id = u.user_id")
        quiz_results = cursor.fetchall()

        # Query to get the skill counts
        cursor.execute("SELECT skill, COUNT(*) as count FROM cv_skills GROUP BY skill ORDER BY count DESC")
        skill_counts = cursor.fetchall()

        # Query to get the skill scores for all users with user ID and rank
        cursor.execute(
            "SELECT u.user_id, u.username, SUM(c.count) AS total_skill_count FROM (SELECT cv_file_id, COUNT(*) AS count FROM cv_skills GROUP BY cv_file_id) AS c JOIN cv_files f ON c.cv_file_id = f.id JOIN users u ON f.user_id = u.user_id GROUP BY u.user_id, u.username ORDER BY total_skill_count DESC")
        skill_scores = cursor.fetchall()

        cursor.close()

        # Determine the correct answers
        correct_answers = {
            'q1': 'A',
            'q2': 'B',
            'q3': 'C',
            'q4': 'A',
            'q5': 'A',
            'q6': 'C',
            'q7': 'A',
            'q8': 'A',
            'q9': 'A',
            'q10': 'A'
        }

        # Calculate the scores for each user
        user_scores = []
        for result in quiz_results:
            user_id = result[0]
            username = result[1]
            user_answers = result[2:]
            score = sum(answer == correct_answers[f'q{i+1}'] for i, answer in enumerate(user_answers))
            user_scores.append((user_id, username, score))

        # Sort the user scores in descending order
        user_scores.sort(key=lambda x: x[2], reverse=True)

        return render_template('leaderboard.html', user_scores=user_scores, skill_counts=skill_counts, skill_scores=skill_scores)
    else:
        flash('You need to login first!', 'error')
        return redirect(url_for('login'))




# Add the cv_view route
@app.route('/cv_view')
def cv_view():
    if 'loggedin' in session:
        # Fetch the list of uploaded CVs for the current user
        cursor = create_mysql_connection()
        cursor.execute('SELECT file_name FROM cv_files WHERE user_id = %s', (session['user_id'],))
        cv_files = cursor.fetchall()
        cursor.close()

        # Pass the list of CV files to the template
        return render_template('cv_view.html', cv_files=cv_files)
    else:
        flash('You need to login first!', 'error')
        return redirect(url_for('login'))


# Add the route for rendering every CV information
@app.route('/all_cv_info')
def all_cv_info():
    if 'loggedin' in session:
        cursor = create_mysql_connection()

        # Query to fetch CV information for all users
        cursor.execute("""
            SELECT u.username, c.file_name,
                   GROUP_CONCAT(DISTINCT cs.skill ORDER BY cs.cv_file_id) AS skills,
                   GROUP_CONCAT(DISTINCT edu.sentence ORDER BY edu.education_id) AS education,
                   GROUP_CONCAT(DISTINCT exp.sentence ORDER BY exp.experience_id) AS experience
            FROM users u
            JOIN cv_files c ON u.user_id = c.user_id
            LEFT JOIN cv_skills cs ON c.id = cs.cv_file_id
            LEFT JOIN cv_education edu ON c.id = edu.cv_file_id
            LEFT JOIN cv_experience exp ON c.id = exp.cv_file_id
            GROUP BY u.username, c.file_name
        """)

        cv_info = cursor.fetchall()

        cursor.close()

        return render_template('all_cv_info.html', cv_info=cv_info)
    else:
        flash('You need to login first!', 'error')
        return redirect(url_for('login'))



# Add the route for rendering every CV information with cvs
@app.route('/every_cv_view')
def every_cv_view():
    if 'loggedin' in session:
        cursor = create_mysql_connection()

        # Query to fetch CV information for all users
        cursor.execute("SELECT u.username, c.file_name, cs.skill, edu.education, exp.experience "
                       "FROM users u "
                       "JOIN cv_files c ON u.user_id = c.user_id "
                       "LEFT JOIN (SELECT cv_file_id, GROUP_CONCAT(skill) AS skill FROM cv_skills GROUP BY cv_file_id) cs ON c.user_id = cs.cv_file_id "
                       "LEFT JOIN (SELECT cv_file_id, GROUP_CONCAT(sentence) AS education FROM (SELECT cv_file_id, sentence FROM cv_education) AS education_table GROUP BY cv_file_id) edu ON c.user_id = edu.cv_file_id "
                       "LEFT JOIN (SELECT cv_file_id, GROUP_CONCAT(sentence) AS experience FROM (SELECT cv_file_id, sentence FROM cv_experience) AS experience_table GROUP BY cv_file_id) exp ON c.user_id = exp.cv_file_id")
        cv_info = cursor.fetchall()

        cursor.close()

        return render_template('every_cv_view.html', cv_info=cv_info)
    else:
        flash('You need to login first!', 'error')
        return redirect(url_for('login'))



@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']

        hashed_password = generate_password_hash(password)

        cursor = create_mysql_connection()
        cursor.execute('INSERT INTO users (username, email, password) VALUES (%s, %s, %s)', (username, email, hashed_password))
        mysql.connection.commit()
        cursor.close()

        flash('You are successfully registered!', 'success')
        return redirect(url_for('login'))
    return render_template('signup.html')



@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        cursor = create_mysql_connection()
        cursor.execute('SELECT * FROM users WHERE username = %s', (username,))
        user = cursor.fetchone()

        if user:
            # Check if cursor.description is not None
            if cursor.description:
                cols = [col[0] for col in cursor.description]
                user_dict = dict(zip(cols, user))

                if check_password_hash(user_dict['password'], password):
                    session['loggedin'] = True
                    session['user_id'] = user_dict['user_id']
                    session['username'] = user_dict['username']
                    flash('Logged in successfully!', 'success')
                    if user_dict['username'] == ADMIN_USERNAME:
                        return redirect(url_for('admin_dashboard'))
                    else:
                        return redirect(url_for('dashboard'))
                else:
                    flash('Invalid username or password!', 'error')
            else:
                flash('Error retrieving user data.', 'error')
        else:
            flash('Invalid username or password!', 'error')

        cursor.close()

    return render_template('login.html')



@app.route('/logout')
def logout():
    session.pop('loggedin', None)
    session.pop('user_id', None)
    session.pop('username', None)
    flash('Logged out successfully!', 'success')
    return redirect(url_for('index'))

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email']
        # Implement forgot password functionality here (e.g., send email with reset link)
        flash('Password reset instructions sent to your email.', 'success')
        return redirect(url_for('login'))
    return render_template('forgot_password.html')


@app.route('/quiz')
def quiz():
    return render_template('quiz.html')

@app.route('/submit_quiz', methods=['POST'])
def submit_quiz():
    if request.method == 'POST':
        # Get quiz answers from form data
        answers = {
            'q1': request.form['q1'],
            'q2': request.form['q2'],
            'q3': request.form['q3'],
            'q4': request.form['q4'],
            'q5': request.form['q5'],
            'q6': request.form['q6'],
            'q7': request.form['q7'],
            'q8': request.form['q8'],
            'q9': request.form['q9'],
            'q10': request.form['q10'],
            # Add more questions here
        }

        # Example: Saving quiz answers to MySQL database
        cursor = create_mysql_connection()
        cursor.execute("INSERT INTO quiz (user_id, q1_answer, q2_answer, q3_answer, q4_answer, q5_answer, q6_answer, q7_answer, q8_answer, q9_answer, q10_answer) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                       (session['user_id'], answers['q1'], answers['q2'], answers['q3'], answers['q4'], answers['q5'], answers['q6'], answers['q7'], answers['q8'], answers['q9'], answers['q10']))
        mysql.connection.commit()
        cursor.close()

        flash('Quiz submitted successfully!', 'success')
        return redirect(url_for('quiz_result'))  # Redirect to quiz_result page

#@app.route('/quiz_result')
#def quiz_result():
    # Calculate quiz result or display result page
#    return render_template('quiz_result.html')

@app.route('/quiz_result')
def quiz_result():
    # Fetch quiz results from the database
    cursor = create_mysql_connection()
    cursor.execute("SELECT q1_answer, q2_answer, q3_answer, q4_answer, q5_answer, q6_answer, q7_answer, q8_answer, q9_answer, q10_answer FROM quiz WHERE user_id = %s", (session['user_id'],))
    quiz_result = cursor.fetchone()
    cursor.close()

    # Check if quiz_result is not None
    if quiz_result:
        # Unpack the quiz result tuple
        q1_answer, q2_answer, q3_answer, q4_answer, q5_answer, q6_answer, q7_answer, q8_answer, q9_answer, q10_answer = quiz_result

        # Determine the correct answers
        correct_answers = {
            'q1': 'A',
            'q2': 'B',
            'q3': 'C',
            'q4': 'A',
            'q5': 'A',
            'q6': 'C',
            'q7': 'A',
            'q8': 'A',
            'q9': 'A',
            'q10': 'A'
        }

        # Calculate the score
        score = 0
        for i in range(1, 11):
            question = f'q{i}_answer'
            user_answer = locals()[question]
            correct_answer = correct_answers[f'q{i}']
            if user_answer == correct_answer:
                score += 1

        # Pass the score and user answers to the template
        return render_template('quiz_result.html', score=score, user_answers=quiz_result)
    else:
        flash('No quiz result found.', 'error')
        return redirect(url_for('dashboard'))


# Modify the analysis_result route in your main.py
@app.route('/analysis_result')
def analysis_result():
    if 'loggedin' in session:
        cursor = create_mysql_connection()

        # Query to get the quiz results for all users
        cursor.execute("SELECT u.user_id, u.username, q.q1_answer, q.q2_answer, q.q3_answer, q.q4_answer, q.q5_answer, q.q6_answer, q.q7_answer, q.q8_answer, q.q9_answer, q.q10_answer FROM quiz q JOIN users u ON q.user_id = u.user_id")
        quiz_results = cursor.fetchall()

        # Query to get the skill counts
        cursor.execute("SELECT skill, COUNT(*) as count FROM cv_skills GROUP BY skill ORDER BY count DESC")
        skill_counts = cursor.fetchall()

        # Query to get the skill scores for all users with user ID and rank
        cursor.execute(
            "SELECT u.user_id, u.username, SUM(c.count) AS total_skill_count FROM (SELECT cv_file_id, COUNT(*) AS count FROM cv_skills GROUP BY cv_file_id) AS c JOIN cv_files f ON c.cv_file_id = f.id JOIN users u ON f.user_id = u.user_id GROUP BY u.user_id, u.username ORDER BY total_skill_count DESC")
        skill_scores = cursor.fetchall()

        cursor.close()

        # Determine the correct answers
        correct_answers = {
            'q1': 'A',
            'q2': 'B',
            'q3': 'C',
            'q4': 'A',
            'q5': 'A',
            'q6': 'C',
            'q7': 'A',
            'q8': 'A',
            'q9': 'A',
            'q10': 'A'
        }

        # Calculate the scores for each user
        user_scores = []
        for result in quiz_results:
            user_id = result[0]
            username = result[1]
            user_answers = result[2:]
            score = sum(answer == correct_answers[f'q{i+1}'] for i, answer in enumerate(user_answers))
            user_scores.append((user_id, username, score))

        # Sort the user scores in descending order
        user_scores.sort(key=lambda x: x[2], reverse=True)

        # Prepare data for pie charts
        quiz_scores_data = [(rank, username, score) for rank, (user_id, username, score) in enumerate(user_scores, start=1)]
        skill_scores_data = [(rank, username, total_skill_count) for rank, (user_id, username, total_skill_count) in enumerate(skill_scores, start=1)]
        skill_counts_data = [(skill, count) for skill, count in skill_counts]

        return render_template('analysis_result.html', quiz_scores_data=quiz_scores_data, skill_scores_data=skill_scores_data, skill_counts_data=skill_counts_data)
    else:
        flash('You need to login first!', 'error')
        return redirect(url_for('login'))



if __name__ == '__main__':
    app.run(debug=True)