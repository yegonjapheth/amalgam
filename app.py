import plotly.graph_objects as go
from fpdf import FPDF
from flask import make_response
import io
import csv
import json
import logging
import os
import secrets
import smtplib
import statistics
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from functools import wraps
from io import BytesIO, StringIO

import bcrypt
import plotly.express as px
import plotly.graph_objs as go
import plotly.io as pio
from asgiref.wsgi import WsgiToAsgi
from dotenv import load_dotenv
from flask import (
    Flask,
    flash,
    g,
    jsonify,
    make_response,
    redirect,
    render_template,
    request,
    send_file,
    send_from_directory,
    session,
    url_for,
)
from flask_login import LoginManager, current_user, login_required
from flask_wtf import FlaskForm
from models import (
    Admin,
    Exam,
    Parent,
    Result,
    Score,
    Student,
    Teacher,
    User,
    Worker,
    db,
)
from peewee import CharField, IntegerField, BooleanField
from peewee import JOIN, DoesNotExist, SqliteDatabase, fn
from playhouse.shortcuts import model_to_dict
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
from werkzeug.security import check_password_hash, generate_password_hash
from wtforms import DateField, IntegerField, PasswordField, StringField
from wtforms.validators import DataRequired, Length, NumberRange

app = Flask(__name__)

app.secret_key = secrets.token_hex(16)
login_manager = LoginManager(app)
login_manager.login_view = "login"

logging.basicConfig(
    filename="app.log",
    level=logging.DEBUG,  # Adjust the level as needed
    format="%(asctime)s %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

db.connect()
db.create_tables([Parent, Teacher, Student, Exam,
                 Result, Score, Worker, Admin])


@app.before_request
def before_request():
    g.db = db
    if g.db.is_closed():
        g.db.connect()


@app.teardown_appcontext
def close_db(error):
    if not g.db.is_closed():
        g.db.close()


# Utility functions
def get_exams():
    return Exam.select()


def get_exam_by_id(exam_id):
    return Exam.get_by_id(exam_id)


def get_students():
    return Student.select()


def get_teachers():
    return Teacher.select()


def get_student_by_id(student_id):
    return Student.get_by_id(student_id)


def get_parents():
    return Parent.select()


def get_workers():
    return Worker.select()


def get_results():
    query = (
        Result.select(Result, Exam, Student)
        .join(Exam)
        .join(Student)
        .order_by(Result.exam)
    )
    return query


def get_results_by_exam_id(exam_id):
    return (
        Result.select(Student.name, Result.score)
        .join(Student)
        .where(Result.exam == exam_id)
    )


def get_results_by_student_id(student_id):
    return (
        Result.select(Exam.exam_subject, Result.result_score)
        .join(Exam)
        .where(Result.student == student_id)
        .order_by(Exam.exam_subject)
    )


def calculate_grade(score):
    if score >= 80:
        return "A"
    elif score >= 75:
        return "A-"
    elif score >= 70:
        return "B+"
    elif score >= 65:
        return "B"
    elif score >= 60:
        return "B-"
    elif score >= 55:
        return "C+"
    elif score >= 50:
        return "C"
    elif score >= 45:
        return "C-"
    elif score >= 40:
        return "D+"
    elif score >= 35:
        return "D"
    elif score >= 30:
        return "D-"
    else:
        return "E"


def calculate_total_score(results):
    return sum(result.result_score for result in results)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def is_admin(teacher_id):
    try:
        teacher = Teacher.get(Teacher.id == teacher_id)
        return (
            teacher.is_admin
        )  # Ensure you have an `is_admin` field in the Teacher model
    except DoesNotExist:
        return False


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "teacher_id" not in session:
            return redirect(url_for("login_teacher"))
        return f(*args, **kwargs)

    return decorated_function


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "teacher_id" not in session or not is_admin(session["teacher_id"]):
            return redirect(
                url_for("login_teacher")
            )  # Redirect to a default page or an error page
        return f(*args, **kwargs)

    return decorated_function


@app.route("/")
def index():
    app.logger.info("Home page accessed")
    return render_template("index.html")


@app.route("/wazazis")
def wazazis():
    # Check if 'parent_id' is in the session
    if "parent_id" not in session:
        # Redirect to login if not logged in
        return redirect(url_for("login_parent"))

    # Fetch the parent using 'parent_id' from the session
    parent_id = session["parent_id"]
    parent = Parent.get_by_id(parent_id)

    # Fetch the results for the parent's children
    results = (
        Result.select(Result, Student, Exam)
        .join(Student)  # Join Result with Student
        .switch(Result)  # Switch back to Result
        .join(Exam)  # Join Result with Exam
        .where(Student.parent == parent)
    )  # Filter by parent

    return render_template("wazazi.html", results=results)

@app.route("/download_results/<format>")
def download_results(format):
    # Check if 'parent_id' is in the session
    if "parent_id" not in session:
        # Redirect to login if not logged in
        return redirect(url_for("login_parent"))

    # Fetch the parent using 'parent_id' from the session
    parent_id = session["parent_id"]
    parent = Parent.get_by_id(parent_id)

    # Fetch the results for the parent's children
    results = (
        Result.select(Result, Student, Exam)
        .join(Student)  # Join Result with Student
        .switch(Result)  # Switch back to Result
        .join(Exam)  # Join Result with Exam
        .where(Student.parent == parent)
    )  # Filter by parent

    if format == "csv":
        # Create CSV
        si = StringIO()
        cw = csv.writer(si)
        cw.writerow(["Student Name", "Exam Name", "Score", "Exam Date"])
        for result in results:
            cw.writerow([result.student.name, result.exam.name,
                         result.score, result.exam.date])
        output = si.getvalue()
        response = send_file(
            BytesIO(output.encode("utf-8")),
            as_attachment=True,
            download_name="results.csv",
            mimetype="text/csv",
        )
        return response

    elif format == "pdf":
        # Create PDF
        pdf = FPDF()
        pdf.add_page()

        # Set font for the header
        pdf.set_font("Arial", "B", 12)

        # Set header cells with adjusted column widths
        pdf.cell(50, 10, "Student Name", border=1)
        pdf.cell(60, 10, "Exam Name", border=1)
        pdf.cell(30, 10, "Score", border=1)
        pdf.cell(40, 10, "Exam Date", border=1)
        pdf.ln()  # New line after the header row

        # Set font for the body
        pdf.set_font("Arial", "", 12)

        # Add data rows
        for result in results:
            pdf.cell(50, 10, result.student.name, border=1)
            pdf.cell(60, 10, result.exam.name, border=1)
            pdf.cell(30, 10, str(result.score), border=1)
            pdf.cell(40, 10, result.exam.date.strftime("%Y-%m-%d"), border=1)
            pdf.ln()

        # Write PDF to a BytesIO object
        pdf_output = BytesIO()
        pdf_output.write(pdf.output(dest="S").encode("latin1"))
        pdf_output.seek(0)

        return send_file(
            pdf_output,
            as_attachment=True,
            download_name="results.pdf",
            mimetype="application/pdf",
        )

    else:
        return "Invalid format", 400

@app.route("/admin")
@login_required
@admin_required
def admin():
    # Query to get exam results along with student and exam data
    query = (
        Result.select(
            Result, Student.name.alias("student_name"), Exam.name.alias("exam_name")
        )
        .join(Student, on=(Result.student_id == Student.id))
        .join(Exam, on=(Result.exam_id == Exam.id))
        .order_by(Exam.date.desc())
    )

    results = list(query.dicts())

    # Data preparation for visualizations
    student_scores = []
    for result in results:
        student_scores.append(
            {
                "Exam": result["exam_name"],
                "Student": result["student_name"],
                "Score": result["score"],
            }
        )

    # Create bar chart for average scores by exam
    exam_avg_scores = (
        Result.select(
            Exam.name.alias("exam_name"), fn.AVG(
                Result.score).alias("avg_score")) .join(Exam) .group_by(
            Exam.id) .dicts())

    exam_avg_chart = px.bar(
        list(exam_avg_scores),
        x="exam_name",
        y="avg_score",
        title="Average Scores by Exam",
        labels={"exam_name": "Exam", "avg_score": "Average Score"},
    )
    exam_avg_chart_html = exam_avg_chart.to_html(full_html=False)

    # Create pie chart for score distribution
    score_distribution = px.pie(
        student_scores,
        names="Student",
        values="Score",
        title="Score Distribution Among Students",
    )
    score_distribution_html = score_distribution.to_html(full_html=False)

    # Pass the results and visualizations to the template
    app.logger.info("Admin page accessed")
    return render_template(
        "admin.html",
        results=results,
        exam_avg_chart_html=exam_avg_chart_html,
        score_distribution_html=score_distribution_html,
    )


@app.route("/admin_register", methods=["GET", "POST"])
def admin_register():
    if request.method == "POST":
        username = request.form["username"]
        phone = request.form["phone"]
        password = request.form["password"]
        hashed_password = generate_password_hash(password)

        try:
            # Save the new admin to the database
            Admin.create(
                username=username,
                phone=phone,
                password=hashed_password)
            flash("Admin registered successfully!", "success")
            return redirect(url_for("admin_login"))
        except BaseException:
            flash("Username already exists.", "danger")
    app.logger.info("Admin_register page accessed")
    return render_template("admin_register.html")


@app.route("/admin_login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        phone = request.form["phone"]
        password = request.form["password"]

        try:
            admin = Admin.get(Admin.phone == phone)
            if check_password_hash(admin.password, password):
                session["admin"] = phone
                flash("Login successful!", "success")
                return redirect(url_for("admin_dashboard"))
            else:
                flash("Invalid username or password", "danger")
        except Admin.DoesNotExist:
            flash("Invalid username or password", "danger")
    app.logger.info("Admin_login page accessed")
    return render_template("admin_login.html")


@app.route("/admin_dashboard")
def admin_dashboard():
    if "admin" not in session:
        return redirect(url_for("admin_login"))
    admins = Admin.select()
    app.logger.info("Admin_dashboard page accessed")
    return render_template("admin_dashboard.html", admins=admins)


@app.route("/edit_admin/<int:admin_id>", methods=["GET", "POST"])
def edit_admin(admin_id):
    if "admin" not in session:
        return redirect(url_for("admin_login"))

    admin = Admin.get_or_none(Admin.id == admin_id)
    if not admin:
        flash("Admin not found!", "danger")
        return redirect(url_for("admin_dashboard"))

    if request.method == "POST":
        username = request.form["username"]
        phone = request.form["phone"]
        password = request.form["password"]

        admin.username = username
        admin.phone = phone
        if password:
            admin.password = generate_password_hash(password)
        admin.save()

        flash("Admin updated successfully!", "success")
        return redirect(url_for("admin_dashboard"))
    app.logger.info("Edit_admin page accessed")
    return render_template("edit_admin.html", admin=admin)


@app.route("/delete_admin/<int:admin_id>", methods=["POST"])
def delete_admin(admin_id):
    if "admin" not in session:
        return redirect(url_for("admin_login"))

    admin = Admin.get_or_none(Admin.id == admin_id)
    if admin:
        admin.delete_instance()
        flash("Admin deleted successfully!", "success")
    else:
        flash("Admin not found!", "danger")

    app.logger.info("Delete_admin page accessed")
    return redirect(url_for("admin_dashboards"))


@app.route("/admin_logout")
def admin_logout():
    session.pop("admin", None)
    flash("You have been logged out.", "info")

    app.logger.info("Admin_logout page accessed")
    return redirect(url_for("admin_login"))


@app.route("/login_teacher", methods=["GET", "POST"])
def login_teacher():
    if request.method == "POST":
        phone = request.form["phone"]
        password = request.form["password"]

        teacher = Teacher.select().where(Teacher.phone == phone).first()

        if teacher and bcrypt.checkpw(
            password.encode("utf-8"), teacher.password.encode("utf-8")
        ):
            session["teacher_id"] = teacher.id
            session.permanent = True
            return redirect(url_for("index"))
        else:
            return render_template(
                "login_teacher.html",
                current_year=datetime.now().year,
                message="Invalid phone number or password",
            )

    else:
        if "teacher_id" in session:
            return redirect(url_for("sms"))
        app.logger.info("Login_teacher page accessed")
        return render_template("login_teacher.html")


@app.route("/login_parent", methods=["GET", "POST"])
def login_parent():
    if request.method == "POST":
        phone = request.form["phone"]
        password = request.form["password"]
        parent = Parent.select().where(Parent.phone == phone).first()

        if parent and check_password_hash(parent.password, password):
            session["parent_id"] = parent.id
            return redirect(url_for("wazazi"))
        else:
            return "Invalid credentials", 401

    app.logger.info("Login_parent page accessed")
    return render_template("login_parent.html")


@app.route("/exam_results/<int:exam_id>")
# @login_required
def exam_results(exam_id):
    exam = get_exam_by_id(exam_id)
    results = get_results_by_exam_id(exam_id)
    results_list = list(results)

    # Calculate average score
    if results_list:
        scores = [result.score for result in results_list]
        average_score = statistics.mean(scores)
    else:
        average_score = 0

    # Generate a bar chart
    fig = go.Figure(
        data=[
            go.Bar(
                x=[result.student.name for result in results_list],
                y=[result.score for result in results_list],
            )
        ]
    )
    fig.update_layout(
        title=f"{exam.name} Results",
        xaxis_title="Learner Name",
        yaxis_title="Score")
    graph_html = fig.to_html(full_html=False)

    app.logger.info("Exam_results page accessed")
    return render_template(
        "exam_results.html",
        exam=exam,
        results=results_list,
        average_score=average_score,
        graph_html=graph_html,
    )


@app.route("/export_csv/<int:student_id>")
@login_required
def export_csv(student_id):
    student = Student.get_or_none(Student.id == student_id)
    if not student:
        flash("Student not found", "error")
        return redirect(url_for("students"))

    results = (
        Result.select(Result, Exam)
        .join(Exam)
        .where(Result.student == student)
        .order_by(Exam.date)
    )

    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(["Exam Name", "Date", "Score", "Grade"])

    for result in results:
        cw.writerow(
            [
                result.exam.name,
                result.exam.date.strftime("%Y-%m-%d"),
                result.score,
                calculate_grade(result.score),
            ]
        )

    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = (
        f"attachment; filename=exam_results_{student.name}.csv"
    )
    output.headers["Content-type"] = "text/csv"
    app.logger.info("Export_csv page accessed")
    return output


@app.route("/export_pdf/<int:student_id>")
@login_required
def export_pdf(student_id):
    student = Student.get_or_none(Student.id == student_id)
    if not student:
        flash("Student not found", "error")
        return redirect(url_for("students"))

    results = (
        Result.select(Result, Exam)
        .join(Exam)
        .where(Result.student == student)
        .order_by(Exam.date)
    )

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []

    data = [["Exam Name", "Date", "Score", "Grade"]]
    for result in results:
        data.append(
            [
                result.exam.name,
                result.exam.date.strftime("%Y-%m-%d"),
                str(result.score),
                calculate_grade(result.score),
            ]
        )

    table = Table(data)
    style = TableStyle(
        [
            ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 14),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
            ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
            ("TEXTCOLOR", (0, 1), (-1, -1), colors.black),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 1), (-1, -1), 12),
            ("TOPPADDING", (0, 1), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 1), (-1, -1), 6),
            ("GRID", (0, 0), (-1, -1), 1, colors.black),
        ]
    )
    table.setStyle(style)
    elements.append(table)

    doc.build(elements)

    pdf = buffer.getvalue()
    buffer.close()
    response = make_response(pdf)
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = (
        f"attachment; filename=exam_results_{student.name}.pdf"
    )
    app.logger.info("Export_pdf page accessed")
    return response


@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        message = request.form["message"]

        # Basic validation
        if not name or not email or not message:
            return "All fields are required", 400

        # Email setup from environment variables
        smtp_server = "smtp.gmail.com"  # Replace with your SMTP server
        smtp_port = 587  # Typically 587 for TLS
        smtp_user = os.getenv("SMTP_USER")
        smtp_password = os.getenv("SMTP_PASSWORD")

        # Email details
        msg = MIMEMultipart()
        msg["From"] = smtp_user
        msg["To"] = smtp_user
        msg["Subject"] = "Contact Form Submission"

        # Email body
        body = f"Name: {name}\nEmail: {email}\n\nMessage:\n{message}"
        msg.attach(MIMEText(body, "plain"))

        # Send email
        try:
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls()  # Upgrade to a secure encrypted connection
                server.login(smtp_user, smtp_password)
                server.sendmail(msg["From"], [msg["To"]], msg.as_string())
            return redirect(url_for("contact"))
        except Exception as e:
            return f"An error occurred: {e}", 500

    app.logger.info("Contact page accessed")
    return render_template("contact.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "")
        email = request.form.get("email", "")
        phone = request.form.get("phone", "")
        password = request.form.get("password", "")

        if not name or not email or not password:
            return "Missing required fields", 400

        hashed_password = generate_password_hash(
            password, method="pbkdf2:sha256")

        Parent.create(
            name=name,
            email=email,
            phone=phone,
            password=hashed_password)
    parent = Parent.select()
    app.logger.info("Parent_register page accessed")
    return render_template("register.html", parents=parents)


@app.route("/favicon.ico")
def favicon():
    return send_from_directory(app.static_folder, "favicon.ico")


@app.route("/sms", methods=["GET", "POST"])
def sms():
    current_year = datetime.now().year
    if "teacher_id" in session:
        return render_template("base.html")
    else:
        app.logger.info("SMS page accessed")
        return redirect(url_for("login_teacher"))


@app.route("/about", methods=["GET", "POST"])
def about():
    app.logger.info("About page accessed")
    return render_template("about.html")


@app.route("/services", methods=["GET", "POST"])
def services():
    app.logger.info("Services page accessed")
    return render_template("services.html")


@app.route("/forgot_password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        phone = request.form["phone"]
        teacher = Teacher.select().where(Teacher.phone == phone).first()
        if teacher:
            return render_template("reset_password.html", teacher=teacher)
        else:
            return render_template(
                "forgot_password.html",
                error="Invalid phone number")
    else:
        app.logger.info("Forgot_password page accessed")
        return render_template("forgot_password.html")


@app.route("/reset_password", methods=["POST"])
def reset_password():
    if request.method == "POST":
        teacher_id = request.form["teacher_id"]
        new_password = request.form["new_password"]
        hashed_password = bcrypt.hashpw(
            new_password.encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")
        Teacher.update(password=hashed_password).where(
            Teacher.id == teacher_id
        ).execute()
        app.logger.info("Reset_password page accessed")
        return redirect(url_for("login_teacher"))


@app.route("/teachers", methods=["GET", "POST"])
def teachers():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        phone = request.form.get("phone")
        password = request.form.get("password")
        hashed_password = generate_password_hash(
            password, method="pbkdf2:sha256")
        Teacher.create(
            name=name,
            email=email,
            phone=phone,
            password=hashedpassword)
        return redirect(url_for("teachers"))

    teachers = Teacher.select()
    app.logger.info("Teachers page accessed")
    return render_template("teachers.html", teachers=teachers)


@app.route("/edit_teacher/<int:teacher_id>", methods=["GET", "POST"])
# @login_required
def edit_teacher(teacher_id):
    teacher = Teacher.get_or_none(teacher_id)
    if not teacher:
        return "Teacher not found", 404

    if request.method == "POST":
        teacher.name = request.form["name"]
        teacher.email = request.form["email"]
        teacher.phone = request.form["phone"]
        teacher.password = request.form["password"]
        teacher.save()
        return redirect(url_for("teachers"))

    app.logger.info("Edit_teacher page accessed")
    return render_template("edit_teacher.html", teacher=teacher)


@app.route("/delete_teacher/<int:teacher_id>", methods=["POST"])
@admin_required
def delete_teacher(teacher_id):
    teacher = Teacher.get_or_none(teacher_id)
    if teacher:
        teacher.delete_instance()
    app.logger.info("Delete_teacher page accessed")
    return redirect(url_for("teachers"))


@app.route("/students", methods=["GET", "POST"])
def students():
    if request.method == "POST":
        name = request.form["name"]
        grade = request.form["grade"]
        parent_id = request.form.get("parent_id")
        Student.create(name=name, grade=grade, parent=parent_id)
        return redirect(url_for("students"))

    students = Student.select()
    parents = Parent.select()
    app.logger.info("Learners page accessed")
    return render_template("students.html", students=students, parents=parents)


@app.route("/students/edit/<int:student_id>", methods=["GET", "POST"])
@login_required
def edit_student(student_id):
    student = Student.get_by_id(student_id)
    if request.method == "POST":
        student.name = request.form.get("name")
        student.grade = request.form.get("grade")
        student.parent = request.form.get("parent_id")
        student.save()
        return redirect(url_for("students"))
    parents = Parent.select()
    app.logger.info("Edit_learner page accessed")
    return render_template(
        "edit_student.html",
        student=student,
        parents=parents)


@app.route("/students/delete/<int:student_id>", methods=["GET"])
@admin_required
def delete_student(student_id):
    student = Student.get_by_id(student_id)
    student.delete_instance()
    app.logger.info("Delete_learner page accessed")
    return redirect(url_for("students"))


@app.route("/exams", methods=["GET", "POST"])
def exams():
    if request.method == "POST":
        name = request.form["name"]
        date = request.form["date"]
        teacher_id = request.form["teacher_id"]
        Exam.create(name=name, date=date, teacher_id=teacher_id)
        return redirect(url_for("exams"))

    exams = Exam.select()
    teachers = Teacher.select()
    app.logger.info("Exams page accessed")
    return render_template("exams.html", exams=exams, teachers=teachers)


@app.route("/edit_exam/<int:exam_id>", methods=["GET", "POST"])
@login_required
def edit_exam(exam_id):
    exam = Exam.get_or_none(Exam.id == exam_id)
    if not exam:
        return "Exam not found", 404

    if request.method == "POST":
        exam.name = request.form.get("name")
        exam.date = request.form.get("date")
        exam.teacher_id = request.form.get("teacher_id")
        exam.save()
        flash("Exam updated successfully!")
        return redirect(url_for("exams"))

    teachers = Teacher.select()
    print(teachers)  # Debugging line
    app.logger.info("Edit_exam page accessed")
    return render_template("edit_exam.html", exam=exam, teachers=teachers)


@app.route("/delete_exam/<int:exam_id>", methods=["POST"])
@login_required
@admin_required
def delete_exam(exam_id):
    exam = Exam.get_or_none(exam_id)
    if exam:
        exam.delete_instance()
    app.logger.info("Delete_exam page accessed")
    return redirect(url_for("exams"))


@app.route("/scores")
def scores():
    try:
        # Fetch results with related student and exam data
        results = (
            Result.select(Result, Student, Exam)
            .join(Student, on=(Result.student == Student.id))
            .join(Exam, on=(Result.exam == Exam.id))
        )

        app.logger.info("Scores page accessed")
        return render_template("scores.html", results=results)
    except Exception as e:
        return str(e), 500


@app.route("/add_score", methods=["GET", "POST"])
@login_required
def add_score():
    if request.method == "POST":
        student_id = request.form["student_id"]
        exam_id = request.form["exam_id"]
        score = request.form["score"]

        # Create a new Result entry
        Result.create(student=student_id, exam=exam_id, score=score)

        return redirect(url_for("scores"))

    # Fetch students and exams to populate the form
    students = Student.select()
    exams = Exam.select()

    app.logger.info("Add_scores page accessed")
    return render_template("add_score.html", students=students, exams=exams)


@app.route("/edit_score/<int:score_id>", methods=["GET", "POST"])
@login_required
def edit_score(score_id):
    score = Result.get_or_none(score_id)
    if not score:
        return "Score not found", 404

    if request.method == "POST":
        score.score = request.form["score"]
        score.save()
        return redirect(url_for("scores"))

    app.logger.info("Edit_score page accessed")
    return render_template("edit_score.html", score=score)


@app.route("/delete_score/<int:score_id>", methods=["POST"])
@login_required
@admin_required
def delete_score(score_id):
    score = Result.get_or_none(score_id)
    if score:
        score.delete_instance()
    app.logger.info("Delete_score page accessed")
    return redirect(url_for("scores"))


@app.route("/results")
def results():
    query = (
        Result.select()
        .join(Student, on=(Result.student == Student.id))
        .join(Exam, on=(Result.exam == Exam.id))
    )

    results_list = [result for result in query]

    app.logger.info("Results page accessed")
    return render_template("results.html", results=results_list)


@app.route("/edit_result/<int:id>", methods=["GET", "POST"])
@login_required
def edit_result(id):
    result = Result.get(Result.id == id)

    if request.method == "POST":
        new_score = request.form["score"]
        try:
            with db.atomic():  # Ensure transaction
                result.score = new_score
                result.save()
            return redirect(url_for("results"))
        except Exception as e:
            # Handle exception, log error, etc.
            print(f"Error: {e}")
            return "An error occurred."

    app.logger.info("Edit_result page accessed")
    return render_template("edit_result.html", result=result)


@app.route("/delete_result/<int:result_id>", methods=["POST"])
@login_required
def delete_result(result_id):
    result = Result.get_or_none(result_id)
    if result:
        result.delete_instance()
    app.logger.info("Delete_result page accessed")
    return redirect(url_for("results"))


@app.route("/workers", methods=["GET", "POST"])
def workers():
    workers = Worker.select()
    app.logger.info("Workers page accessed")
    return render_template("workers.html", workers=workers)


@app.route("/parents", methods=["GET", "POST"])
def parents():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        phone = request.form.get("phone")
        password = request.form.get("password")
        hashed_password = generate_password_hash(
            password, method="pbkdf2:sha256")
        Parent.create(
            name=name,
            email=email,
            phone=phone,
            password=hashed_password)
        return redirect(url_for("parents"))

    parents = Parent.select()
    app.logger.info("Parents page accessed")
    return render_template("parents.html", parents=parents)


@app.route("/edit_parent/<int:parent_id>", methods=["GET", "POST"])
@login_required
def edit_parent(parent_id):
    parent = Parent.get_or_none(parent_id)
    if not parent:
        return "Parent not found", 404

    if request.method == "POST":
        parent.name = request.form["name"]
        parent.email = request.form["email"]
        parent.phone = request.form["phone"]
        parent.password = request.form["password"]
        parent.save()
        return redirect(url_for("parents"))

    app.logger.info("Edit_parent page accessed")
    return render_template("edit_parent.html", parent=parent)


@app.route("/delete_parent/<int:parent_id>", methods=["POST"])
@login_required
@admin_required
def delete_parent(parent_id):
    parent = Parent.get_or_none(parent_id)
    if parent:
        parent.delete_instance()
    app.logger.info("Delete_parent page accessed")
    return redirect(url_for("parents"))

@app.route("/wazazi")
def wazazi():
    if "parent_id" not in session:
        return redirect(url_for("login_parent"))

    parent_id = session["parent_id"]
    parent = Parent.get_by_id(parent_id)

    # Fetch the list of students for the logged-in parent
    students = Student.select().where(Student.parent == parent_id)

    # Prepare student results and Plotly graphs
    student_results = {}
    bar_graphs = {}
    pie_graphs = {}

    for student in students:
        # Fetch results and related exams
        results = (
            Result.select(Result.score, Exam.name.alias("exam_name"))
            .join(Exam)
            .where(Result.student == student)
            .dicts()
        )

        student_results[student.id] = results

        # Create Bar chart
        exam_names = [result["exam_name"] for result in results]
        scores = [result["score"] for result in results]

        if exam_names:
            bar_fig = go.Figure(data=[go.Bar(x=exam_names, y=scores)])
            bar_fig.update_layout(
                title=f"{student.name} - Bar Chart",
                xaxis_title="Exam",
                yaxis_title="Score",
            )
            bar_graph_html = pio.to_html(bar_fig, full_html=False)
            bar_graphs[student.id] = bar_graph_html

            # Create Pie chart
            pie_fig = go.Figure(
                data=[
                    go.Pie(
                        labels=exam_names,
                        values=scores)])
            pie_fig.update_layout(title=f"{student.name} - Pie Chart")
            pie_graph_html = pio.to_html(pie_fig, full_html=False)
            pie_graphs[student.id] = pie_graph_html

    app.logger.info("Wazazi page accessed")
    return render_template(
        "dashboard.html",
        parent=parent,
        students=students,
        student_results=student_results,
        bar_graphs=bar_graphs,
        pie_graphs=pie_graphs,
    )

@app.route("/learner_report/<int:student_id>")
def learner_report(student_id):
    if "parent_id" not in session:
        return redirect(url_for("login_parent"))

    parent_id = session["parent_id"]
    student = Student.get_or_none(
        (Student.id == student_id) & (Student.parent == parent_id)
    )
    if not student:
        return "Student not found or you don't have permission to view this report", 404

    # Fetch results for the student
    results = (
        Result.select(Result.score, Exam.name.alias("exam_name"))
        .join(Exam)
        .where(Result.student == student_id)
        .dicts()
    )

    # Create Bar chart
    exam_names = [result["exam_name"] for result in results]
    scores = [result["score"] for result in results]

    bar_fig = go.Figure(data=[go.Bar(x=exam_names, y=scores)])
    bar_fig.update_layout(
        title=f"{student.name} (Bar Chart)",
        xaxis_title="Exam",
        yaxis_title="Score")
    bar_graph_html = pio.to_html(bar_fig, full_html=False)

    # Create Pie chart
    pie_fig = go.Figure(data=[go.Pie(labels=exam_names, values=scores)])
    pie_fig.update_layout(title=f"{student.name} (Pie Chart)")
    pie_graph_html = pio.to_html(pie_fig, full_html=False)

    app.logger.info("Learner_report page accessed")
    return render_template(
        "learner_report.html",
        student=student,
        bar_graph=bar_graph_html,
        pie_graph=pie_graph_html,
    )

@app.route("/learner_results/<int:student_id>")
def learner_results(student_id):
    if "parent_id" not in session:
        return redirect(url_for("login_parent"))

    parent_id = session["parent_id"]
    student = Student.get_or_none(
        (Student.id == student_id) & (Student.parent == parent_id)
    )
    if not student:
        return (
            "Student not found or you don't have permission to view these results",
            404,
        )

    # Fetch results for the student
    results = (
        Result.select(Result.score, Exam.name.alias("exam_name"))
        .join(Exam)
        .where(Result.student == student_id)
        .dicts()
    )

    app.logger.info("Learner_results page accessed")
    return render_template(
        "learner_results.html",
        student=student,
        results=results)


@app.route("/add_worker", methods=["GET", "POST"])
@login_required
def add_worker():
    if request.method == "POST":
        name = request.form["name"]
        id_no = request.form["id_no"]
        phone = request.form["phone"]
        job = request.form["job"]
        Worker.create(
            name=name,
            id_no=id_no,
            phone=phone,
            job=job,
        )
        return redirect(url_for("workers"))
    app.logger.info("Add_worker page accessed")
    return render_template("add_worker.html")


@app.route("/edit_worker/<int:worker_id>", methods=["GET", "POST"])
@login_required
def edit_worker(worker_id):
    worker = Worker.get_by_id(worker_id)

    if request.method == "POST":
        try:
            name = request.form["name"]
            id_no = request.form["id_no"]
            phone = request.form["phone"]
            job = request.form["job"]
            worker.name = name
            worker.id_no = id_no
            worker.phone = phone
            worker.job = job
            worker.save()
            flash("Worker updated successfully!")
            logging.info(f"Worker updated: ID {worker_id}, Name {worker.name}")
            return redirect(url_for("workers"))
        except Exception as e:
            logging.error(f"Error updating worker: {e}")
            flash("Error updating worker. Please try again.")

    app.logger.info("Edit_worker page accessed")
    return render_template("edit_worker.html", worker=worker)


@app.route("/delete_worker/<int:worker_id>", methods=["POST"])
@login_required
@admin_required
def delete_worker(worker_id):
    try:
        worker = Worker.get_by_id(worker_id)
        worker.delete_instance()
        flash("Worker deleted successfully!")
        logging.info(f"Worker deleted: Name: {worker.name}")
    except Exception as e:
        logging.error(f"Error deleting worker: {e}")
        flash("Error deleting worker. Please try again.")
    app.logger.info("Delete_worker page accessed")
    return redirect(url_for("workers"))


@app.route("/manage_users")
@admin_required
def manage_users():
    # Functionality for managing users
    teachers = Teacher.select()
    students = Student.select()
    workers = Worker.select()
    parents = Parent.select()
    exams = Exam.select()
    results = Result.select()
    app.logger.info("Manage_users page accessed")
    return render_template(
        "manage_users.html",
        teachers=teachers,
        students=students,
        workers=workers,
        parents=parents,
        exams=exams,
        results=results,
    )


@app.route("/edits_teacher/<int:teacher_id>", methods=["GET", "POST"])
@admin_required
def edits_teacher(teacher_id):
    teacher = Teacher.get_by_id(teacher_id)
    if request.method == "POST":
        teacher.name = request.form["name"]
        teacher.email = request.form["email"]
        teacher.phone = request.form["phone"]
        teacher.password = bcrypt.hashpw(
            request.form["password"].encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")
        teacher.is_admin = "is_admin" in request.form  # Update admin status
        teacher.save()
        flash("Teacher updated successfully!")
        return redirect(url_for("manage_users"))
    app.logger.info("Edits_teacher page accessed")
    return render_template("edits_teacher.html", teacher=teacher)


@app.route("/logout_teacher")
def logout_teacher():
    session.pop("teacher_id", None)  # Remove the teacher_id from the session
    app.logger.info("Logout_teacher page accessed")
    return redirect(url_for("login_teacher"))


@app.route("/logout_parent")
def logout_parent():
    session.pop("parent_id", None)
    app.logger.info("Logout_parent page accessed")
    return redirect(url_for("login_parent"))


if __name__ == "__main__":
    app.run(port=5000, debug=True, host="0.0.0.0")
