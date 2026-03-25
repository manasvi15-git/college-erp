import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
# Secret key for session management (Keep this secure in production!)
app.secret_key = 'super_secret_key' 

# Configure SQLite Database
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ==========================================
# DATABASE SCHEMAS (MODELS)
# ==========================================

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False) # Roles: 'admin', 'teacher', 'student'
    
    # Optional relationship linking a User account to Student details
    student_details = db.relationship('Student', backref='user', uselist=False)

class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    roll_number = db.Column(db.String(20), unique=True, nullable=False)
    course = db.Column(db.String(50), nullable=False)

class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(10), nullable=False) # 'Present', 'Absent'
    
class Marks(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    subject = db.Column(db.String(50), nullable=False)
    marks_obtained = db.Column(db.Integer, nullable=False)
    total_marks = db.Column(db.Integer, nullable=False)

# Auto-create the database and populate an initial Admin user
with app.app_context():
    db.create_all()
    # Check if admin already exists
    if not User.query.filter_by(username='admin').first():
        hashed_pw = generate_password_hash('admin123')
        admin = User(username='admin', password=hashed_pw, role='admin')
        db.session.add(admin)
        db.session.commit()

# ==========================================
# ROUTES & VIEWS
# ==========================================

@app.route('/')
def index():
    # If the user is already logged in, send them straight to the dashboard
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    # If a logged-in user tries to visit /register, redirect them to dashboard
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        # Retrieve data from the registration form
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']

        # Check if the username is already taken
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Username already exists. Please choose a different one.', 'warning')
            return redirect(url_for('register'))

        # Hash the password for security
        hashed_password = generate_password_hash(password)
        
        # Create a new User object and save it to the database
        new_user = User(username=username, password=hashed_password, role=role)
        db.session.add(new_user)
        db.session.commit()

        flash('Registration successful! You can now log in.', 'success')
        return redirect(url_for('login'))

    # If it's a GET request, just show the registration form
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Retrieve data from the login form
        username = request.form['username']
        password = request.form['password']
        
        # Search the database for the user
        user = User.query.filter_by(username=username).first()
        
        # Check if the user exists and the password hashes match
        if user and check_password_hash(user.password, password):
            # Save user identity in the current browsing session
            session['user_id'] = user.id
            session['username'] = user.username
            session['role'] = user.role
            
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password', 'danger')
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    # Clear the entire session to log out
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    # Protect this route: only logged-in users enter
    if 'user_id' not in session:
        flash('Please log in to access the dashboard.', 'warning')
        return redirect(url_for('login'))
        
    # Pass necessary details to the template based on who is logged in
    role = session['role']
    username = session['username']
    
    return render_template('dashboard.html', role=role, username=username)

# ==========================================
# STUDENT MANAGEMENT
# ==========================================

@app.route('/students')
def students():
    # Only Admin and Teachers can view the full student list
    if 'user_id' not in session or session.get('role') not in ['admin', 'teacher']:
        flash('Access denied. You must be an admin or teacher.', 'danger')
        return redirect(url_for('dashboard'))
        
    all_students = Student.query.all()
    return render_template('students.html', students=all_students)

@app.route('/students/add', methods=['GET', 'POST'])
def add_student():
    # Only Admin can add students
    if 'user_id' not in session or session.get('role') != 'admin':
        flash('Admin access required to add students.', 'danger')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        user_id = request.form['user_id']
        name = request.form['name']
        roll_number = request.form['roll_number']
        course = request.form['course']

        new_student = Student(user_id=user_id, name=name, roll_number=roll_number, course=course)
        db.session.add(new_student)
        db.session.commit()
        
        flash('Student added successfully!', 'success')
        return redirect(url_for('students'))
    
    # Get all users who have the role 'student' but aren't linked to a Student record yet
    existing_student_user_ids = [s.user_id for s in Student.query.all()]
    unlinked_users = User.query.filter_by(role='student').filter(User.id.notin_(existing_student_user_ids)).all()
    
    return render_template('add_student.html', users=unlinked_users)

@app.route('/students/edit/<int:id>', methods=['GET', 'POST'])
def edit_student(id):
    if 'user_id' not in session or session.get('role') != 'admin':
        flash('Admin access required to edit students.', 'danger')
        return redirect(url_for('dashboard'))
        
    student = Student.query.get_or_404(id)
    
    if request.method == 'POST':
        student.name = request.form['name']
        student.roll_number = request.form['roll_number']
        student.course = request.form['course']
        
        db.session.commit()
        flash('Student updated successfully!', 'success')
        return redirect(url_for('students'))
        
    return render_template('edit_student.html', student=student)

@app.route('/students/delete/<int:id>', methods=['POST'])
def delete_student(id):
    if 'user_id' not in session or session.get('role') != 'admin':
        flash('Admin access required to delete students.', 'danger')
        return redirect(url_for('dashboard'))
        
    student = Student.query.get_or_404(id)
    db.session.delete(student)
    db.session.commit()
    
    flash('Student deleted successfully!', 'info')
    return redirect(url_for('students'))

# ==========================================
# ATTENDANCE SYSTEM
# ==========================================

@app.route('/attendance/mark', methods=['GET', 'POST'])
def mark_attendance():
    if 'user_id' not in session or session.get('role') not in ['admin', 'teacher']:
        flash('Access denied. Only Teachers and Admins can mark attendance.', 'danger')
        return redirect(url_for('dashboard'))
        
    date_str = request.args.get('date') or datetime.today().strftime('%Y-%m-%d')
    try:
        selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        selected_date = datetime.today().date()
        
    students = Student.query.all()
    
    # Get existing attendance for this date
    existing_records = Attendance.query.filter_by(date=selected_date).all()
    attendance_map = {record.student_id: record.status for record in existing_records}
    
    if request.method == 'POST':
        # The form will submit student_id as key and 'Present'/'Absent' as value
        for student in students:
            status = request.form.get(f'status_{student.id}')
            if status:
                if student.id in attendance_map:
                    record = Attendance.query.filter_by(student_id=student.id, date=selected_date).first()
                    record.status = status
                else:
                    new_record = Attendance(student_id=student.id, date=selected_date, status=status)
                    db.session.add(new_record)
        db.session.commit()
        flash(f'Attendance saved for {selected_date}!', 'success')
        return redirect(url_for('mark_attendance', date=selected_date))
        
    return render_template('mark_attendance.html', students=students, selected_date=selected_date, attendance_map=attendance_map)

@app.route('/attendance/report')
def attendance_report():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    role = session.get('role')
    
    if role == 'student':
        # A student can only see their own report
        student = Student.query.filter_by(user_id=session['user_id']).first()
        if not student:
            flash('No student profile linked to your account. Contact Admin.', 'warning')
            return redirect(url_for('dashboard'))
            
        records = Attendance.query.filter_by(student_id=student.id).order_by(Attendance.date.desc()).all()
        return render_template('attendance_report.html', student=student, records=records)
        
    else: # Admin or Teacher
        student_id = request.args.get('student_id')
        students = Student.query.all()
        
        if student_id:
            student = Student.query.get(student_id)
            records = Attendance.query.filter_by(student_id=student_id).order_by(Attendance.date.desc()).all()
            return render_template('attendance_report.html', students=students, selected_student=student, records=records)
            
        # If no student selected, just show the page with dropdown
        return render_template('attendance_report.html', students=students)

# ==========================================
# MARKS MANAGEMENT SYSTEM
# ==========================================

@app.route('/marks/add', methods=['GET', 'POST'])
def add_marks():
    if 'user_id' not in session or session.get('role') not in ['admin', 'teacher']:
        flash('Access denied. Only Teachers and Admins can add marks.', 'danger')
        return redirect(url_for('dashboard'))
        
    students = Student.query.all()
    
    if request.method == 'POST':
        student_id = request.form['student_id']
        subject = request.form['subject']
        marks_obtained = int(request.form['marks_obtained'])
        total_marks = int(request.form['total_marks'])
        
        new_mark = Marks(
            student_id=student_id, 
            subject=subject, 
            marks_obtained=marks_obtained, 
            total_marks=total_marks
        )
        db.session.add(new_mark)
        db.session.commit()
        
        flash('Marks uploaded successfully!', 'success')
        return redirect(url_for('add_marks'))
        
    return render_template('add_marks.html', students=students)

@app.route('/marks/report')
def view_marks():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    role = session.get('role')
    
    if role == 'student':
        # Student views own marks
        student = Student.query.filter_by(user_id=session['user_id']).first()
        if not student:
            flash('No student profile linked to your account. Contact Admin.', 'warning')
            return redirect(url_for('dashboard'))
            
        student_marks = Marks.query.filter_by(student_id=student.id).all()
        return render_template('view_marks.html', student=student, marks=student_marks)
        
    else: # Admin or Teacher
        student_id = request.args.get('student_id')
        students = Student.query.all()
        
        if student_id:
            student = Student.query.get(student_id)
            student_marks = Marks.query.filter_by(student_id=student_id).all()
            return render_template('view_marks.html', students=students, selected_student=student, marks=student_marks)
            
        return render_template('view_marks.html', students=students)

if __name__ == '__main__':
    # Run the Flask app in debug mode (helpful during development)
    app.run(debug=True)
