import json
import os
import secrets
from functools import wraps

from flask import Flask, abort, redirect, render_template, request, session, url_for

from model import Alternativa, Pergunta, Quiz, Tentativa, Usuario, db

app = Flask(__name__)

app.config["SECRET_KEY"] = "segredo_super_simples"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///banco.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

with app.app_context():
    db.create_all()


def login_obrigatorio(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if "usuario_id" not in session:
            return redirect(url_for("login"))
        return func(*args, **kwargs)

    return wrapper


def gerar_slug():
    while True:
        slug = secrets.token_urlsafe(8).replace("-", "").replace("_", "")[:10]
        if not Quiz.query.filter_by(slug=slug).first():
            return slug


def montar_link_publico(slug):
    return request.url_root.rstrip("/") + url_for("responder_quiz", slug=slug)


def buscar_quiz_do_usuario(slug):
    quiz = Quiz.query.filter_by(slug=slug, usuario_id=session["usuario_id"]).first()
    if not quiz:
        abort(404)
    return quiz


def validar_payload_quiz(payload_bruto):
    if not payload_bruto:
        return None, "Adicione perguntas no quiz."

    try:
        payload = json.loads(payload_bruto)
    except json.JSONDecodeError:
        return None, "Dados inválidos. Atualize a página e tente novamente."

    if not isinstance(payload, list) or not payload:
        return None, "Adicione pelo menos 1 pergunta válida."

    perguntas_validas = []
    for item in payload:
        if not isinstance(item, dict):
            return None, "Formato de pergunta inválido."

        texto = str(item.get("texto", "")).strip()
        alternativas_brutas = item.get("alternativas", [])
        if not isinstance(alternativas_brutas, list):
            return None, "Formato de alternativas inválido."

        alternativas = [str(alt).strip() for alt in alternativas_brutas if str(alt).strip()][:4]
        indice_correta = item.get("correta")

        if (
            not texto
            or len(alternativas) < 2
            or not isinstance(indice_correta, int)
            or indice_correta < 0
            or indice_correta >= len(alternativas)
        ):
            return (
                None,
                "Cada pergunta precisa de texto, no mínimo 2 alternativas e uma resposta correta.",
            )

        perguntas_validas.append(
            {
                "texto": texto,
                "alternativas": alternativas[:4],
                "correta": indice_correta,
            }
        )

    return perguntas_validas, None


def salvar_perguntas_quiz(quiz, perguntas_validas, substituir=False):
    if substituir:
        perguntas_atuais = Pergunta.query.filter_by(quiz_id=quiz.id).all()
        for pergunta in perguntas_atuais:
            db.session.delete(pergunta)
        db.session.flush()

    for indice_pergunta, pergunta in enumerate(perguntas_validas, start=1):
        nova_pergunta = Pergunta(
            quiz_id=quiz.id,
            texto=pergunta["texto"],
            ordem=indice_pergunta,
        )
        db.session.add(nova_pergunta)
        db.session.flush()

        for indice_alt, texto_alt in enumerate(pergunta["alternativas"]):
            db.session.add(
                Alternativa(
                    pergunta_id=nova_pergunta.id,
                    texto=texto_alt,
                    correta=indice_alt == pergunta["correta"],
                )
            )


def serializar_quiz_para_form(quiz):
    perguntas = []
    for pergunta in sorted(quiz.perguntas, key=lambda item: item.ordem):
        alternativas = list(pergunta.alternativas)
        correta = 0
        textos_alternativas = []

        for indice, alternativa in enumerate(alternativas):
            textos_alternativas.append(alternativa.texto)
            if alternativa.correta:
                correta = indice

        perguntas.append(
            {
                "texto": pergunta.texto,
                "alternativas": textos_alternativas,
                "correta": correta,
            }
        )

    return perguntas


@app.route("/")
@login_obrigatorio
def home():
    quizzes = (
        Quiz.query.filter_by(usuario_id=session["usuario_id"])
        .order_by(Quiz.criado_em.desc())
        .all()
    )
    return render_template(
        "home.html",
        seusuario_nome=session["usuario_nome"],
        usuario_email=session["usuario_email"],
        quizzes=quizzes,
    )


@app.route("/register", methods=["GET", "POST"])
def register():
    erro = None

    if request.method == "POST":
        nome = request.form["nome"].strip()
        email = request.form["email"].strip().lower()
        senha = request.form["senha"].strip()

        if not nome or not email or not senha:
            erro = "Preencha todos os campos."
        elif Usuario.query.filter_by(email=email).first():
            erro = "Esse email já está em uso."
        else:
            novo_usuario = Usuario(nome=nome, email=email, senha=senha)
            db.session.add(novo_usuario)
            db.session.commit()
            return redirect(url_for("login"))

    return render_template("register.html", erro=erro)


@app.route("/login", methods=["GET", "POST"])
def login():
    erro = None

    if request.method == "POST":
        email = request.form["email"].strip().lower()
        senha = request.form["senha"].strip()

        usuario = Usuario.query.filter_by(email=email, senha=senha).first()

        if usuario:
            session["usuario_id"] = usuario.id
            session["usuario_nome"] = usuario.nome
            session["usuario_email"] = usuario.email
            return redirect(url_for("home"))

        erro = "Login inválido."

    return render_template("login.html", erro=erro)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/quiz/novo", methods=["GET", "POST"])
@login_obrigatorio
def criar_quiz():
    erro = None
    titulo_inicial = ""
    perguntas_iniciais = []

    if request.method == "POST":
        titulo_inicial = request.form.get("titulo", "").strip()
        payload_bruto = request.form.get("payload", "").strip()

        if not titulo_inicial:
            erro = "Informe um título para o quiz."
        else:
            perguntas_validas, erro = validar_payload_quiz(payload_bruto)

            if not erro:
                novo_quiz = Quiz(
                    titulo=titulo_inicial,
                    slug=gerar_slug(),
                    usuario_id=session["usuario_id"],
                )
                db.session.add(novo_quiz)
                db.session.flush()

                salvar_perguntas_quiz(novo_quiz, perguntas_validas)
                db.session.commit()
                return redirect(url_for("detalhes_quiz", slug=novo_quiz.slug))

    return render_template(
        "create_quiz.html",
        erro=erro,
        page_mode="create",
        quiz=None,
        titulo_inicial=titulo_inicial,
        perguntas_iniciais=perguntas_iniciais,
    )


@app.route("/quiz/<slug>/editar", methods=["GET", "POST"])
@login_obrigatorio
def editar_quiz(slug):
    quiz = buscar_quiz_do_usuario(slug)
    erro = None
    titulo_inicial = quiz.titulo
    perguntas_iniciais = serializar_quiz_para_form(quiz)

    if request.method == "POST":
        titulo_inicial = request.form.get("titulo", "").strip()
        payload_bruto = request.form.get("payload", "").strip()

        if not titulo_inicial:
            erro = "Informe um título para o quiz."
        else:
            perguntas_validas, erro = validar_payload_quiz(payload_bruto)

            if not erro:
                quiz.titulo = titulo_inicial
                salvar_perguntas_quiz(quiz, perguntas_validas, substituir=True)
                db.session.commit()
                return redirect(url_for("detalhes_quiz", slug=quiz.slug))

    return render_template(
        "create_quiz.html",
        erro=erro,
        page_mode="edit",
        quiz=quiz,
        titulo_inicial=titulo_inicial,
        perguntas_iniciais=perguntas_iniciais,
    )


@app.route("/quiz/<slug>/deletar", methods=["POST"])
@login_obrigatorio
def deletar_quiz(slug):
    quiz = buscar_quiz_do_usuario(slug)
    db.session.delete(quiz)
    db.session.commit()
    return redirect(url_for("home"))


@app.route("/quiz/<slug>/detalhes")
@login_obrigatorio
def detalhes_quiz(slug):
    quiz = buscar_quiz_do_usuario(slug)

    ranking = (
        Tentativa.query.filter_by(quiz_id=quiz.id)
        .order_by(Tentativa.pontuacao.desc(), Tentativa.criado_em.asc())
        .limit(10)
        .all()
    )

    return render_template(
        "quiz_detalhes.html",
        quiz=quiz,
        link_publico=montar_link_publico(quiz.slug),
        ranking=ranking,
    )


@app.route("/quiz/<slug>", methods=["GET", "POST"])
def responder_quiz(slug):
    quiz = Quiz.query.filter_by(slug=slug).first_or_404()
    perguntas = (
        Pergunta.query.filter_by(quiz_id=quiz.id)
        .order_by(Pergunta.ordem.asc())
        .all()
    )
    erro = None

    if request.method == "POST":
        participante_nome = request.form.get("nome", "").strip()
        if not participante_nome:
            erro = "Digite seu nome para continuar."
        else:
            total_perguntas = len(perguntas)
            pontuacao = 0

            for pergunta in perguntas:
                resposta_marcada = request.form.get(f"pergunta_{pergunta.id}")
                correta = next(
                    (alternativa for alternativa in pergunta.alternativas if alternativa.correta),
                    None,
                )

                if resposta_marcada and correta and resposta_marcada.isdigit():
                    if int(resposta_marcada) == correta.id:
                        pontuacao += 1

            tentativa = Tentativa(
                quiz_id=quiz.id,
                participante_nome=participante_nome[:80],
                pontuacao=pontuacao,
                total_perguntas=total_perguntas,
            )
            db.session.add(tentativa)
            db.session.commit()

            return redirect(
                url_for("resultado_quiz", slug=quiz.slug, tentativa_id=tentativa.id)
            )

    return render_template("take_quiz.html", quiz=quiz, perguntas=perguntas, erro=erro)


@app.route("/quiz/<slug>/resultado/<int:tentativa_id>")
def resultado_quiz(slug, tentativa_id):
    quiz = Quiz.query.filter_by(slug=slug).first_or_404()
    tentativa = Tentativa.query.filter_by(id=tentativa_id, quiz_id=quiz.id).first_or_404()

    ranking_completo = (
        Tentativa.query.filter_by(quiz_id=quiz.id)
        .order_by(Tentativa.pontuacao.desc(), Tentativa.criado_em.asc())
        .all()
    )
    ranking = ranking_completo[:20]

    posicao = None
    for indice, item in enumerate(ranking_completo, start=1):
        if item.id == tentativa.id:
            posicao = indice
            break

    return render_template(
        "quiz_result.html",
        quiz=quiz,
        tentativa=tentativa,
        ranking=ranking,
        posicao=posicao,
    )


@app.route("/quiz/<slug>/ranking")
def ranking_quiz(slug):
    quiz = Quiz.query.filter_by(slug=slug).first_or_404()
    ranking = (
        Tentativa.query.filter_by(quiz_id=quiz.id)
        .order_by(Tentativa.pontuacao.desc(), Tentativa.criado_em.asc())
        .limit(100)
        .all()
    )
    return render_template("ranking.html", quiz=quiz, ranking=ranking)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
