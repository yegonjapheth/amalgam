from peewee import *

# Database configuration
db = SqliteDatabase("school.db")


class BaseModel(Model):
    class Meta:
        database = db

# Define the Admin model
class Admin(BaseModel):
    username = CharField(unique=True)
    phone = IntegerField()
    password = CharField()


class Parent(BaseModel):
    name = CharField()
    email = CharField(unique=True)
    phone = CharField(null=True)
    password = CharField()


class Teacher(BaseModel):
    name = CharField()
    email = CharField(unique=True)
    phone = CharField(null=True)
    password = CharField()
    is_admin = BooleanField(default=False)


class Student(BaseModel):
    name = CharField()
    grade = CharField(unique=True)
    parent = ForeignKeyField(Parent, backref="students")


class Exam(BaseModel):
    name = CharField()
    date = DateField()
    teacher = ForeignKeyField(Teacher, backref="exams")


class Result(BaseModel):
    student = ForeignKeyField(Student, backref="results")
    exam = ForeignKeyField(Exam, backref="results")
    score = IntegerField()


class Score(BaseModel):
    student = ForeignKeyField(Student, backref="scores")
    exam = ForeignKeyField(Exam, backref="scores")
    score = IntegerField()


class Worker(BaseModel):
    name = CharField()
    id_no = IntegerField()
    phone = CharField()
    job = CharField()


# Ensure database and tables are created
if __name__ == "__main__":
    db.connect()
    db.create_tables([Parent, Teacher, Student, Exam, Result])
