from datetime import datetime

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    senha = db.Column(db.String(100), nullable=False)
    quizzes = db.relationship("Quiz", backref="criador", lazy=True)


class Quiz(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(140), nullable=False)
    slug = db.Column(db.String(32), unique=True, nullable=False, index=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuario.id"), nullable=False)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    perguntas = db.relationship(
        "Pergunta",
        backref="quiz",
        lazy=True,
        cascade="all, delete-orphan",
        order_by="Pergunta.ordem",
    )
    tentativas = db.relationship(
        "Tentativa",
        backref="quiz",
        lazy=True,
        cascade="all, delete-orphan",
    )


class Pergunta(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey("quiz.id"), nullable=False)
    texto = db.Column(db.Text, nullable=False)
    ordem = db.Column(db.Integer, nullable=False, default=1)
    alternativas = db.relationship(
        "Alternativa",
        backref="pergunta",
        lazy=True,
        cascade="all, delete-orphan",
        order_by="Alternativa.id",
    )


class Alternativa(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    pergunta_id = db.Column(db.Integer, db.ForeignKey("pergunta.id"), nullable=False)
    texto = db.Column(db.String(255), nullable=False)
    correta = db.Column(db.Boolean, default=False, nullable=False)


class Tentativa(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey("quiz.id"), nullable=False)
    participante_nome = db.Column(db.String(80), nullable=False)
    pontuacao = db.Column(db.Integer, nullable=False, default=0)
    total_perguntas = db.Column(db.Integer, nullable=False, default=0)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
