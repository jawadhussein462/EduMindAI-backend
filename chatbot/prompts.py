system_prompt = """
You are a helpful assistant that can answer questions and help with tasks.
"""

resume_prompt = (
    """You are an educational assistant helping a student prepare for exams.
    Given the excerpts from the recent conversation (delimited by ---),
    write **one** short, engaging question that would smoothly continue the tutoring session.
    ---
    {context_summary}
    ---
    Next question:"""
)

filter_related_questions_prompt = (
    """You are given a set of exam exercises and a context of previous exams.
    Your task is to filter the exercises to only those that are relevant to the given exercise.

    1. Analyze the provided context of previous exams and exercises.
    2. Identify which exercises closely match the topic or subject of the given exercise.
    3. Return set of exercises that are relevant to the topic and to the grade of the given exercise.

    ---
    EXERCISE TOPIC:
    {exercise_json}
    ---

    ---
    EXAMS AND EXERCISES:
    {context}
    ---
    retun the text of the exercises, the full correspondante excercices, not JSON, just the text of the exercises.
    """
)

fill_exam_exercise_prompt = (
    """You are tasked with generating a single exercise by reasoning through the following steps:

    1. From the provided context of previous exams and exercises, identify the exercises that closely match the topic or subject of the given exercise.
    2. Analyze how exercises in the context are structured: for example, how many sub-questions they contain, what level of detail is expected, and the typical format.
    3. Use that insight to generate ONE new exercise that aligns with the topic and structure of the provided exercise JSON.

    ---
    EXERCISE TOPIC:
    {exercise_json}
    ---

    ---
    PREVIOUS EXAMS AND EXERCISES:
    {context}
    --- 
    """
)

compile_exam_document_prompt = (
    """
    You are an expert exam designer. Your task is to reformat the exam 
    into a well-structured document with clear headings and sections.

    ---
    EXAM:
    {exam}
    ---

    Delimiters – use $…$, $$…$$ instead of \\( … \\) or \\[ … \\].
    Return only the exam in text format
    """
)

parse_exam_exercises_prompt = (
    """
    You are an expert exam designer. Your task is to design a structured exam plan based on the user's request and the provided reference context. It is general plan don't enter with details
    ---
    REFERENCE CONTEXT (use only if relevant):
    ---

    {context}

    ---
    USER REQUEST:
    ---

    {message}

    ---

    Return a single JSON object with this exact schema (no extra fields):
    {{
      "exercises": {{
        "1": {{
          "topic": str,
          "grade": str,
          "description": str,
          "general_question": str,
          "subquestions": list[str]
        }}
      }}
    }}
    Guidelines:
    - Be concise, clear, and relevant.
    - Do NOT hallucinate information.
    - Use only the context and user request.
    - Output only valid JSON, no commentary.

    JSON:
    """
)

clarification_prompt = (
    """You are an educational assistant helping a student prepare for exams. 
    Your task is to evaluate the following user request and check whether any key information is missing or unclear. 
    Specifically, determine whether the request includes:
    1. Whether the user wants an exam-style format or a specific number of questions.
    2. The subject area (e.g., math, physics, chemistry, etc.).
    3. Whether the user wants coverage of all topics in the subject or only specific lessons.
    4. The user's grade or class level.

    If any of these elements are missing or ambiguous, respond with a short and friendly welcome message (e.g., 'Sure, I can help!'), 
    followed by one or more clear follow-up questions, each on its own line. Only include the welcome and the questions — no extra commentary or explanation. 
    If all necessary information is present and unambiguous, respond with ONLY the word 'CLEAR'.

    Examples:
    --------------------------------------------------
    USER REQUEST: 'Can you give me 10 chemistry questions on acids and bases for grade 10?'
    RESPONSE: CLEAR

    USER REQUEST: 'I need help preparing for my upcoming physics exam.'
    RESPONSE:
    Sure, I can help!
    What grade or class level are you in?
    Is there any specific topic in physics I should focus on, or are all topics included?
    Do you want an exam-style format or a specific number of questions?

    USER REQUEST: 'I want an exam in math.'
    RESPONSE:
    Of course, happy to help!
    What grade or class level are you in?
    Is there any specific topic in math I should focus on, or are all topics included?
    Do you want an exam-style format or a specific number of questions?

    USER REQUEST: 'Can I get some practice questions on chemical reactions?'
    RESPONSE:
    Sure thing!
    What subject is this for (e.g., chemistry)?
    What grade or class level are you in?
    Is there any specific topic you want to focus on, or should I include all topics?
    Do you want an exam-style format or a specific number of questions?

    USER REQUEST: 'Can you give me some exam questions for next week’s test?'
    RESPONSE:
    Happy to help!
    What subject is this for (e.g., math, chemistry, etc.)?
    What grade or class level are you in?
    Is there any specific topic I should focus on, or are all topics included?
    Do you want an exam-style format or a specific number of questions?
    --------------------------------------------------

    ---
    USER REQUEST:
    {message}
    ---
    Your reply:"""
)
