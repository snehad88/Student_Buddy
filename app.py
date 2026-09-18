from flask import Flask, render_template, request, jsonify, session
from google import genai
from dotenv import load_dotenv
import os
import sqlite3
from datetime import datetime
import markdown
import json
import time

from curriculum import NCERT_CURRICULUM


# ============================================================
# Load Environment Variables
# ============================================================

load_dotenv()


# ============================================================
# Flask Application
# ============================================================

app = Flask(__name__)

# Secret key is required for session-based learning context
app.secret_key = os.getenv(
    "FLASK_SECRET_KEY",
    "student-buddy-local-secret"
)


# ============================================================
# Gemini AI
# ============================================================

client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)

GEMINI_MODEL = "gemini-3.5-flash-lite"
GEMINI_MAX_RETRIES = 2
GEMINI_RETRY_DELAYS = [2, 5]


def generate_gemini(prompt):
    """Generate Gemini content with short retries for temporary errors."""
    last_error = None

    for attempt in range(GEMINI_MAX_RETRIES + 1):
        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt
            )

            if not response.text:
                raise ValueError("Gemini returned an empty response.")

            return response.text

        except Exception as e:
            last_error = e
            error_text = str(e).upper()

            retryable = (
                "503" in error_text
                or "UNAVAILABLE" in error_text
                or (
                    "429" in error_text
                    and "PERMINUTE" not in error_text
                    and "PER_DAY" not in error_text
                    and "PERDAY" not in error_text
                )
            )

            if not retryable or attempt >= GEMINI_MAX_RETRIES:
                raise

            delay = GEMINI_RETRY_DELAYS[attempt]
            print(
                f"Gemini temporary error. Retrying in {delay} seconds "
                f"(retry {attempt + 1}/{GEMINI_MAX_RETRIES})..."
            )
            time.sleep(delay)

    raise last_error


# ============================================================
# Database
# ============================================================

DATABASE = "student_buddy.db"


# ============================================================
# Initialize Database
# ============================================================

def init_database():

    connection = sqlite3.connect(DATABASE)

    cursor = connection.cursor()


    # --------------------------------------------------------
    # Learning activity tracking
    # --------------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS learning_activity (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            section TEXT NOT NULL,
            duration INTEGER NOT NULL,
            timestamp TEXT NOT NULL
        )
    """)


    # --------------------------------------------------------
    # AI generated content cache
    # --------------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ai_content_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            feature TEXT NOT NULL,
            subject TEXT NOT NULL,
            chapter TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            UNIQUE(feature, subject, chapter)
        )
    """)


    connection.commit()

    connection.close()


# Create database when application starts
init_database()


# ============================================================
# Learning Context Helper
# ============================================================

def get_learning_context():

    """
    Gets Class, Subject and Chapter from the URL.

    If they are not present in the URL, recover them
    from the Flask session.

    This prevents the selected learning context from
    disappearing when the student moves between pages.
    """

    class_name = request.args.get("class")
    subject = request.args.get("subject")
    chapter = request.args.get("chapter")


    # --------------------------------------------------------
    # Recover from session if missing
    # --------------------------------------------------------

    if not class_name:
        class_name = session.get("class_name")

    if not subject:
        subject = session.get("subject")

    if not chapter:
        chapter = session.get("chapter")


    # --------------------------------------------------------
    # Save current values into session
    # --------------------------------------------------------

    if class_name:
        session["class_name"] = class_name

    if subject:
        session["subject"] = subject

    if chapter:
        session["chapter"] = chapter


    return class_name, subject, chapter


# ============================================================
# Home Page
# ============================================================

@app.route("/")
def home():

    return render_template(
        "index.html"
    )
# =========================
# New Joiner Kit
# =========================

@app.route("/new-joiner")
def new_joiner():
    return render_template("new_joiner.html")

# ============================================================
# Study Buddy
# ============================================================

@app.route("/study")
def study():

    classes = list(
        NCERT_CURRICULUM.keys()
    )


    return render_template(
        "study.html",
        curriculum=NCERT_CURRICULUM,
        classes=classes
    )


# ============================================================
# Learning Page
# ============================================================

@app.route("/learn")
def learn():

    class_name, subject, chapter = (
        get_learning_context()
    )


    return render_template(
        "learn.html",
        class_name=class_name,
        subject=subject,
        chapter=chapter
    )


# ============================================================
# Explain Topic
# ============================================================

@app.route("/explain")
def explain():

    class_name, subject, chapter = (
        get_learning_context()
    )


    # --------------------------------------------------------
    # Validate
    # --------------------------------------------------------

    if not subject or not chapter:

        return render_template(
            "explain.html",
            class_name=class_name,
            subject=subject or "",
            chapter=chapter or "",
            explanation="""
            <h3>Learning information is missing</h3>
            <p>
                Please return to Study Buddy and select
                a class, subject and chapter.
            </p>
            """
        )


    if not class_name:
        class_name = "8"


    # --------------------------------------------------------
    # Cache key
    #
    # We include the Class in the feature name so that:
    #
    # Class 8 Science Light
    #
    # does not accidentally reuse:
    #
    # Class 10 Science Light
    # --------------------------------------------------------

    cache_feature = (
        f"Explain Topic - Class {class_name}"
    )


    # --------------------------------------------------------
    # Check database cache
    # --------------------------------------------------------

    connection = sqlite3.connect(DATABASE)

    cursor = connection.cursor()

    cursor.execute("""
        SELECT content
        FROM ai_content_cache
        WHERE feature = ?
        AND subject = ?
        AND chapter = ?
    """, (
        cache_feature,
        subject,
        chapter
    ))

    cached_result = cursor.fetchone()

    connection.close()


    if cached_result:

        print(
            "Using cached explanation:",
            class_name,
            subject,
            "-",
            chapter
        )

        explanation = cached_result[0]


        return render_template(
            "explain.html",
            class_name=class_name,
            subject=subject,
            chapter=chapter,
            explanation=explanation
        )


    # --------------------------------------------------------
    # Built-in fallback
    # --------------------------------------------------------

    fallback_explanation = None


    if (
        class_name == "8"
        and subject.lower() == "science"
        and chapter.lower() ==
        "crop production and management"
    ):

        fallback_explanation = """

        <h2>What is Crop Production?</h2>

        <p>
        Crop production is the process of growing plants
        for food, fibre and other useful products.
        Farmers follow several important steps to grow
        healthy crops.
        </p>

        <h3>Important Concepts</h3>

        <p><strong>1. Preparation of Soil</strong></p>

        <p>
        The soil is loosened and turned over.
        This helps roots grow easily and allows air
        to enter the soil.
        </p>

        <p><strong>2. Sowing</strong></p>

        <p>
        Healthy seeds are selected and planted in
        properly prepared soil.
        </p>

        <p><strong>3. Manure and Fertilisers</strong></p>

        <p>
        Manure and fertilisers provide nutrients
        needed by plants for healthy growth.
        </p>

        <p><strong>4. Irrigation</strong></p>

        <p>
        Irrigation means supplying water to crops
        at regular intervals.
        </p>

        <p><strong>5. Protection from Weeds</strong></p>

        <p>
        Unwanted plants growing with crops are called
        weeds. Farmers remove them so crops get enough
        water, nutrients, sunlight and space.
        </p>

        <p><strong>6. Harvesting</strong></p>

        <p>
        Harvesting is the process of cutting and
        collecting a mature crop.
        </p>

        <p><strong>7. Storage</strong></p>

        <p>
        Harvested grains must be stored safely to
        protect them from moisture, insects and
        microorganisms.
        </p>

        <h3>Simple Real-Life Example</h3>

        <p>
        Imagine a farmer growing wheat.
        The farmer prepares the soil, sows good-quality
        seeds, waters the crop and removes weeds.
        When the wheat becomes mature, it is harvested
        and stored safely.
        </p>

        <h3>Key Points to Remember</h3>

        <ul>
            <li>Soil is prepared before sowing.</li>
            <li>Healthy seeds help produce healthy crops.</li>
            <li>Irrigation supplies water to crops.</li>
            <li>Weeds compete with crops for resources.</li>
            <li>Harvesting is done when crops mature.</li>
            <li>Proper storage protects harvested grains.</li>
        </ul>

        """


    if fallback_explanation:

        print(
            "Using built-in explanation:",
            class_name,
            subject,
            "-",
            chapter
        )


        return render_template(
            "explain.html",
            class_name=class_name,
            subject=subject,
            chapter=chapter,
            explanation=fallback_explanation
        )


    # --------------------------------------------------------
    # Gemini prompt
    # --------------------------------------------------------

    prompt = f"""
You are Student Buddy, an AI learning assistant
for Class {class_name} students.

The student is studying:

Class: {class_name}
Subject: {subject}
Chapter: {chapter}

Explain this chapter in simple language suitable
for a Class {class_name} student.

Structure your response as:

1. What is this topic?
2. Important concepts
3. A simple real-life example
4. Key points to remember

Use simple words and short paragraphs.

Do not make the explanation too advanced.

Be encouraging and friendly.
"""


    try:

        explanation = generate_gemini(prompt)
        # ----------------------------------------------------
        # Save to cache
        # ----------------------------------------------------

        connection = sqlite3.connect(DATABASE)

        cursor = connection.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO ai_content_cache
            (feature, subject, chapter, content, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """, (
            cache_feature,
            subject,
            chapter,
            explanation,
            datetime.now().isoformat()
        ))

        connection.commit()

        connection.close()


        print(
            "Saved new explanation:",
            class_name,
            subject,
            "-",
            chapter
        )


    except Exception as e:

        print(
            "Gemini Explain Error:",
            e
        )


        explanation = """
        <h3>Explanation temporarily unavailable</h3>

        <p>
        Gemini is temporarily busy, so Student Buddy could not generate
        this explanation right now.
        </p>

        <p>
        Please try again later.
        </p>
        """


    return render_template(
        "explain.html",
        class_name=class_name,
        subject=subject,
        chapter=chapter,
        explanation=explanation
    )


# ============================================================
# Ask Question Page
# ============================================================

@app.route("/ask")
def ask():

    class_name, subject, chapter = (
        get_learning_context()
    )


    return render_template(
        "ask.html",
        class_name=class_name,
        subject=subject,
        chapter=chapter
    )


# ============================================================
# Ask Question - Gemini
# ============================================================

@app.route(
    "/ask-question",
    methods=["POST"]
)
def ask_question():

    # --------------------------------------------------------
    # Get values from submitted form
    # --------------------------------------------------------

    class_name = (
        request.form.get("class")
        or session.get("class_name")
        or "8"
    )

    subject = (
        request.form.get("subject")
        or session.get("subject")
    )

    chapter = (
        request.form.get("chapter")
        or session.get("chapter")
    )

    question = request.form.get(
        "question"
    )


    # Save context again

    session["class_name"] = class_name

    if subject:
        session["subject"] = subject

    if chapter:
        session["chapter"] = chapter


    # --------------------------------------------------------
    # Gemini prompt
    # --------------------------------------------------------

    prompt = f"""
You are Student Buddy, an AI learning assistant
for a Class {class_name} student.

The student is studying:

Class: {class_name}
Subject: {subject}
Chapter: {chapter}

The student asks:

{question}

Answer the student's question in simple language
suitable for Class {class_name}.

Rules:

- Stay relevant to the subject and chapter.
- Explain the concept clearly.
- Use a simple example when helpful.
- Do not use unnecessarily complicated terminology.
- Encourage the student to understand the concept
  rather than simply memorize it.
"""


    try:

        answer = generate_gemini(prompt)
    except Exception as e:

        print(
            "Gemini Question Error:",
            e
        )


        answer = """
        Gemini is temporarily busy, so Student Buddy could not generate
        an answer right now.

        Please try again in a few moments.
        """


    return render_template(
        "answer.html",
        class_name=class_name,
        subject=subject,
        chapter=chapter,
        question=question,
        answer=answer
    )


# ============================================================
# Chapter Summary
# ============================================================

@app.route("/summary")
def summary():

    class_name, subject, chapter = (
        get_learning_context()
    )


    if not subject or not chapter:

        return render_template(
            "summary.html",
            class_name=class_name or "",
            subject=subject or "",
            chapter=chapter or "",
            summary="""
            <h3>Learning information is missing</h3>

            <p>
            Please return to Study Buddy and select
            a class, subject and chapter.
            </p>
            """
        )


    if not class_name:
        class_name = "8"


    # --------------------------------------------------------
    # Gemini prompt
    # --------------------------------------------------------

    prompt = f"""
You are Student Buddy, an AI learning assistant
for Class {class_name} students.

The student is studying:

Class: {class_name}
Subject: {subject}
Chapter: {chapter}

Create a clear, visually organized chapter summary
for a Class {class_name} student.

Use the following structure:

# 📖 What is this chapter about?

Give a short and simple introduction.

# ⭐ Important Concepts

Explain the most important concepts using bullet points.

# 📝 Key Points to Remember

Give 4 to 6 important revision points.

# 🌍 Simple Real-Life Examples

Give 2 or 3 easy examples from everyday life.

# 🎯 Quick Revision

Give a short list of things the student should
remember before an exam.

Rules:

- Use simple Class {class_name} language.
- Use short paragraphs.
- Use bullet points where appropriate.
- Use bold text for important terms.
- Keep the summary concise and easy to revise.
- Do not repeat the same information.
- Do not include unnecessary greetings or motivational messages.
- Do not say "Hello", "Welcome", or "You've got this".
- Do not include a conclusion asking the student what
  they want to learn next.
- Return the answer using Markdown formatting.
"""


    try:

        summary_text = generate_gemini(prompt)
        # Convert Markdown to HTML

        summary_html = markdown.markdown(
            summary_text,
            extensions=["extra"]
        )


    except Exception as e:

        print(
            "Gemini Summary Error:",
            e
        )


        summary_html = """
        <h3>⚠️ Summary temporarily unavailable</h3>

        <p>
        Gemini is temporarily busy, so Student Buddy could not generate
        the summary right now.
        </p>

        <p>
        Please try again in a few moments.
        </p>
        """


    return render_template(
        "summary.html",
        class_name=class_name,
        subject=subject,
        chapter=chapter,
        summary=summary_html
    )


# ============================================================
# Save Learning Activity
# ============================================================

@app.route(
    "/track-time",
    methods=["POST"]
)
def track_time():

    data = request.get_json()


    if not data:

        return jsonify({
            "success": False
        })


    section = data.get(
        "section"
    )

    duration = data.get(
        "duration"
    )


    if not section or not duration:

        return jsonify({
            "success": False
        })


    connection = sqlite3.connect(
        DATABASE
    )

    cursor = connection.cursor()


    cursor.execute("""
        INSERT INTO learning_activity
        (section, duration, timestamp)
        VALUES (?, ?, ?)
    """, (
        section,
        int(duration),
        datetime.now().isoformat()
    ))


    connection.commit()

    connection.close()


    return jsonify({
        "success": True
    })


# ============================================================
# Learning Insights
# ============================================================

@app.route("/insights")
def insights():

    # --------------------------------------------------------
    # Dummy classmate learning times
    # --------------------------------------------------------

    classmates = {

        "Aadya": 38,

        "Rahul": 31,

        "Arushi": 45,

        "Arnav": 29,

        "Rianshi": 36,

        "Kushal": 41,

        "Charvi": 33,

        "Samudyata": 48,

        "Sanidya": 27,

        "Mohik": 39,

        "Nikhil": 35

    }


    # --------------------------------------------------------
    # Get YOUR total learning time
    # --------------------------------------------------------

    connection = sqlite3.connect(
        DATABASE
    )

    cursor = connection.cursor()


    cursor.execute("""
        SELECT SUM(duration)
        FROM learning_activity
    """)


    total_seconds = (
        cursor.fetchone()[0]
        or 0
    )


    # --------------------------------------------------------
    # Get YOUR time by activity
    # --------------------------------------------------------

    cursor.execute("""
        SELECT section, SUM(duration)
        FROM learning_activity
        GROUP BY section
    """)


    rows = cursor.fetchall()


    connection.close()


    # --------------------------------------------------------
    # Convert to minutes
    # --------------------------------------------------------

    your_minutes = (
        total_seconds // 60
    )


    # --------------------------------------------------------
    # Combine You + Classmates
    # --------------------------------------------------------

    all_students = {

        "You": your_minutes,

        **classmates

    }


    # --------------------------------------------------------
    # Class Average
    # --------------------------------------------------------

    class_average = (
        sum(all_students.values())
        / len(all_students)
    )


    # --------------------------------------------------------
    # Difference from Average
    # --------------------------------------------------------

    difference = (
        your_minutes
        - class_average
    )


    # --------------------------------------------------------
    # Highest Learning Time
    # --------------------------------------------------------

    highest_time = max(
        all_students.values()
    )


    highest_student = max(
        all_students,
        key=all_students.get
    )


    # --------------------------------------------------------
    # Format Duration
    # --------------------------------------------------------

    def format_duration(seconds):

        minutes = (
            seconds // 60
        )

        remaining_seconds = (
            seconds % 60
        )


        if minutes >= 60:

            hours = (
                minutes // 60
            )

            minutes = (
                minutes % 60
            )


            return (
                f"{hours}h "
                f"{minutes}m "
                f"{remaining_seconds}s"
            )


        return (
            f"{minutes}m "
            f"{remaining_seconds}s"
        )


    # --------------------------------------------------------
    # Activity List
    # --------------------------------------------------------

    activities = []


    icons = {

        "Study Buddy": "📚",

        "Explain Topic": "📖",

        "Ask a Question": "💡",

        "Summary": "📝",

        "Quiz": "🧠",

        "New Joiner Kit": "🎒"

    }


    for section, seconds in rows:

        activities.append({

            "section": section,

            "duration":
                format_duration(seconds),

            "icon":
                icons.get(
                    section,
                    "📌"
                )

        })


    # --------------------------------------------------------
    # Send Data to insights.html
    # --------------------------------------------------------

    return render_template(

        "insights.html",

        total_time=
            format_duration(
                total_seconds
            ),

        your_minutes=
            your_minutes,

        class_average=
            round(
                class_average
            ),

        difference=
            round(
                difference
            ),

        highest_time=
            highest_time,

        highest_student=
            highest_student,

        students=
            all_students,

        activities=
            activities

    )


# ============================================================
# Quiz Page
# ============================================================

@app.route("/quiz")
def quiz():

    class_name, subject, chapter = (
        get_learning_context()
    )


    return render_template(

        "quiz.html",

        class_name=
            class_name or "8",

        subject=
            subject or "",

        chapter=
            chapter or ""

    )


# ============================================================
# Generate Quiz
# ============================================================

@app.route("/generate-quiz")
def generate_quiz():

    class_name, subject, chapter = (
        get_learning_context()
    )


    if not class_name:
        class_name = "8"


    if not subject or not chapter:

        return jsonify({

            "success": False,

            "error":
                "Class, subject and chapter are required."

        }), 400


    # --------------------------------------------------------
    # Gemini Quiz Prompt
    # --------------------------------------------------------

    prompt = f"""
Create a Class {class_name} level quiz for the
following topic.

Class: {class_name}
Subject: {subject}
Chapter: {chapter}

Create exactly 5 multiple-choice questions.

Each question must have:

- question
- exactly 4 options
- correctAnswer as the zero-based index
  of the correct option

Return ONLY valid JSON in this exact format:

{{
    "questions": [
        {{
            "question": "Question text",
            "options": [
                "Option 1",
                "Option 2",
                "Option 3",
                "Option 4"
            ],
            "correctAnswer": 0
        }}
    ]
}}

Rules:

- Questions must be suitable for Class {class_name} students.
- Use simple and clear language.
- Questions must relate directly to the given chapter.
- Only one option should be correct.
- correctAnswer must be 0, 1, 2, or 3.
- Do not include explanations.
- Do not include Markdown.
- Return only JSON.
"""


    try:

        quiz_text = generate_gemini(prompt).strip()


        # ----------------------------------------------------
        # Remove accidental Markdown code fences
        # ----------------------------------------------------

        if quiz_text.startswith("```"):

            quiz_text = (
                quiz_text
                .replace("```json", "")
                .replace("```", "")
                .strip()
            )


        # ----------------------------------------------------
        # Convert JSON
        # ----------------------------------------------------

        quiz_data = json.loads(
            quiz_text
        )


        if "questions" not in quiz_data:

            raise ValueError(
                "Invalid quiz format."
            )


        return jsonify({

            "success": True,

            "questions":
                quiz_data["questions"]

        })


    except Exception as e:

        print(
            "Gemini Quiz Error:",
            e
        )


        return jsonify({

            "success": False,

            "error":
                "Quiz could not be generated right now. "
                "Gemini is temporarily busy. Please try again in a few moments."

        }), 500


# ============================================================
# Start Flask
# ============================================================

if __name__ == "__main__":

    app.run(
        debug=True
    )
