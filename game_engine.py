#!/usr/bin/env python
# coding: utf-8

# # PROJECT SETUP AND CONFIGURATION

# **1. IMPORTS**

# In[6]:


import random
import json
import time
import os
import uuid

from datetime import datetime, timezone
from google import genai
from getpass import getpass

import streamlit as st


# **2. GEMINI CLIENT CONFIGURATION**

# In[7]:


# Load the API key from environment variables
# If it isn't available, ask the user to enter it securely
if not os.environ.get('GEMINI_API_KEY'):
    os.environ['GEMINI_API_KEY']= st.secrets['GEMINI_API_KEY']

# Initialize the Gemini API client
client = genai.Client()
print('Gemini client initialized successfully!')


# **3. MODEL CONFIGURATION**

# In[8]:


# Model used for puzzle generation and AI reasoning
MODEL_NAME = "gemini-3.5-flash-lite"

print('Selected model: ', MODEL_NAME)


# **4. GAME CONFIGURATIONS**

# In[9]:


# Puzzle categories supported in the current MVP
PUZZLE_CATEGORIES = ['number_pattern','riddle']

# Available difficulty levels, ordered from easiest to hardest
DIFFICULTY_LEVELS = ['easy','medium','hard']

# Every new game session starts at Easy
STARTING_DIFFICULTY = 'easy'

# Maximum number of hints available for each puzzle
MAX_HINTS = 3

# Number of recent puzzles to consider when avoiding repetition
RECENT_HISTORY_LIMIT = 10

# Maximum attempts to generate a puzzle that passes validation
MAX_GENERATION_ATTEMPTS = 3


# # PUZZLE DATA STRUCTURE

# **5. COMMON PUZZLE DATA STRUCTURE**

# In[10]:


def create_puzzle(
    category,
    difficulty,
    question,
    content,
    answer_type,
    correct_answer,
    hints,
    explanation,
    options=None,
    accepted_answers=None,
    source="ai"
):
    """
    Creates a standardized puzzle dictionary.

    All puzzle categories share the same outer structure.
    Category-specific information is stored inside 'content'.

    Parameters:
        category (str): Puzzle category.
        difficulty (str): Difficulty level.
        question (str): Question displayed to the player.
        content (dict): Category-specific puzzle information.
        answer_type (str): Expected answer type.
        correct_answer: The correct answer.
        hints (list): Three progressive hints.
        explanation (str): Explanation of the solution.
        options (list, optional): Multiple-choice options.
        accepted_answers (list, optional): Alternative valid answers.
        source (str): Where the puzzle originated.

    Returns:
        dict: A standardized puzzle object.
    """

    # Generate a unique identifier for each puzzle.
    puzzle_id = str(uuid.uuid4())

    # Create the standardized puzzle structure.
    puzzle = {
        # Identification and classification
        "puzzle_id": puzzle_id,
        "category": category,
        "difficulty": difficulty,

        # Puzzle content
        "question": question,
        "content": content,

        # Answer information
        "answer_type": answer_type,
        "correct_answer": correct_answer,
        "options": options if options is not None else [],
        "accepted_answers": (
            accepted_answers if accepted_answers is not None else []
        ),

        # Player assistance
        "hints": hints,
        "explanation": explanation,

        # Metadata
        "source": source,
        "validation_status": "pending"
    }

    return puzzle


# # PUZZLE GENERATION

# **6. DIFFICULTY GUIDELINES**

# In[11]:


# Guidelines used by Gemini to control puzzle complexity.

PUZZLE_DIFFICULTY_GUIDELINES = {
    "number_pattern": {
        "easy": (
            "Use straightforward patterns such as constant addition, "
            "subtraction, multiplication, or division."
        ),
        "medium": (
            "Use moderately challenging patterns such as alternating "
            "operations, increasing differences, or combinations "
            "of simple operations."
        ),
        "hard": (
            "Use challenging patterns such as multiple interacting "
            "sequences, complex difference patterns, or less obvious "
            "mathematical relationships."
        )
    },

    "riddle": {
        "easy": (
            "Use familiar objects, everyday situations, and "
            "straightforward clues. The answer should be relatively "
            "easy to infer."
        ),
        "medium": (
            "Use more indirect clues, wordplay, and multiple "
            "reasoning steps. The answer should require some thought."
        ),
        "hard": (
            "Use challenging wordplay, layered clues, and less obvious "
            "connections. Avoid obscure trivia or knowledge players "
            "would need to look up."
        )
    }
}


# **7. GEMINI RESPONSE HANDLING**

# In[12]:


def generate_json_response(prompt):
    """
    Sends a prompt to Gemini and returns the response as a Python dictionary.

    Parameters:
        prompt (str): Instructions sent to the Gemini model.

    Returns:
        dict: Parsed JSON response from Gemini.

    Raises:
        ValueError: If Gemini returns an empty or invalid JSON response.
    """

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
        config={
            "response_mime_type": "application/json"
        }
    )

    # Extract the text response.
    response_text = response.text

    # Ensure Gemini returned a response.
    if not response_text:
        raise ValueError("Gemini returned an empty response.")

    # Convert JSON text into a Python dictionary.
    try:
        return json.loads(response_text)

    except json.JSONDecodeError as error:
        raise ValueError(
            f"Gemini returned invalid JSON: {response_text}"
        ) from error


# **8. NUMBER PATTERN PUZZLE**

# In[13]:


# ==========================================
# NUMBER PATTERN PROMPT
# ==========================================

def get_number_pattern_prompt(difficulty, recent_puzzles=None, feedback=None):

    """
    Builds the prompt used to generate a number pattern puzzle.

    Parameters:
        difficulty (str): Requested difficulty.
        recent_puzzles (list): Recent puzzles to avoid repeating.
        feedback (str, optional): Validation errors from a previous attempt.

    Returns:
        str: Prompt for Gemini.
    """

    # Use an empty list if no puzzle history is provided
    recent_puzzles = recent_puzzles or []

    # Retrieve the guidelines for the requested difficulty
    difficulty_guidelines = PUZZLE_DIFFICULTY_GUIDELINES["number_pattern"][difficulty]

    prompt = f"""
    You are an expert puzzle creator for Puzzle Pirates, an adaptive brain puzzle game.
    
    Generate ONE original number pattern puzzle.
    
    DIFFICULTY: {difficulty}
    difficulty_guidelines = {difficulty_guidelines}
    
    PUZZLE REQUIREMENTS:
    
    1. The puzzle must have exactly one missing number.
    2. The sequence must contain at least 4 numbers.
    3. The missing number must be represented as null.
    4. Use a clear and mathematically consistent pattern.
    5. The correct answer must be an integer.
    6. Provide exactly 4 multiple-choice options.
    7. Only one option can be correct.
    8. Provide exactly 3 progressive hints.
    9. Hints must gradually reveal the solving approach without immediately giving away the answer.
    10. Provide a clear explanation of the solution.
    11. Avoid ambiguous sequences with multiple valid answers.
    12. Match the complexity of the requested difficulty.
    
    VARIETY REQUIREMENTS:
    
    - Use different mathematical patterns.
    - Vary the starting numbers and sequence length.
    - Explore addition, subtraction, multiplication, division, alternating patterns, and other valid patterns.
    - Avoid repeatedly generating simple arithmetic sequences.
    - Do not copy the examples or previously generated puzzles.
    
    RECENTLY GENERATED PUZZLES TO AVOID: 
    {json.dumps(recent_puzzles, indent=2)}
    
    Generate something substantially different from these puzzles.
    
    Return ONLY valid JSON using this structure:
    {{
        "category": "number_pattern",
        "difficulty": "{difficulty}",
        "question": "Find the missing number.",
        "content": {{
            "sequence": [3, 6, 9, null, 15],
            "missing_position": 3,
            "pattern_type": "addition"
        }},
        "answer_type": "integer",
        "correct_answer": 12,
        "options": [10, 11, 12, 14],
        "accepted_answers": [],
        "hints": [
            "Hint 1",
            "Hint 2",
            "Hint 3"
        ],
        "explanation": "Explain the pattern and answer."
    }}

    The example above is only a format reference. Generate a new puzzle rather than copying it.
    """

    # Add validation feedback if the previous attempt failed
    if feedback:
        prompt += f"""
    
    PREVIOUS VALIDATION ERRORS:
    {feedback}
    
    Generate a new puzzle and correct all the issues above
    """

    return prompt


# In[14]:


# ==========================================
# NUMBER PATTERN GENERATOR
# ==========================================

def generate_number_pattern(difficulty, recent_puzzles=None, feedback=None):

    """
    Generates a number pattern puzzle using Gemini.

    Parameters:
        difficulty (str): Requested difficulty.
        recent_puzzles (list, optional): Puzzles to avoid repeating.
        feedback (str, optional): Validation feedback.

    Returns:
        dict: Raw puzzle data returned by Gemini.
    """

    # Build the generation prompt 
    prompt = get_number_pattern_prompt(
        difficulty,
        recent_puzzles = recent_puzzles,
        feedback=feedback
    )

    # Generate and parse the JSON response
    generated_data = generate_json_response(prompt)

    return generated_data


# **9. RIDDLE PUZZLE**

# In[15]:


# ==========================================
# RIDDLE PROMPT
# ==========================================

def get_riddle_prompt(difficulty, recent_puzzles=None, feedback=None):

    """
    Builds the prompt used to generate a riddle.

    Parameters:
        difficulty (str): Requested difficulty.
        recent_puzzles (list): Recent riddles to avoid repeating.
        feedback (str, optional): Validation errors from a previous attempt.

    Returns:
        str: Prompt for Gemini.
    """

    # Use an empty list if no puzzle history is provided
    recent_puzzles = recent_puzzles or []

    # Retrieve difficulty-specific guidelines
    difficulty_guidelines = PUZZLE_DIFFICULTY_GUIDELINES['riddle'][difficulty]

    prompt = f"""
    You are an expert riddle creator for Puzzle Pirates, an adaptive brain puzzle game.

    Generate ONE original riddle.

    DIFFICULTY: {difficulty}
    difficulty_guidelines = {difficulty_guidelines}

    PUZZLE REQUIREMENTS:

    1. Generate one clear and engaging riddle.
    2. The riddle must have one intended answer.
    3. Avoid ambiguous clues that support multiple unrelated answers.
    4. Provide the correct answer as a short text string.
    5. Provide alternative accepted answers where appropriate.
    6. Do not include the correct answer in the question.
    7. Generate exactly 3 progressive hints.
    8. Each hint should reveal more information than the previous one.
    9. Hints must not immediately reveal the answer.
    10. Provide a clear explanation of the answer.
    11. Avoid obscure trivia and culturally specific references.
    12. Generate an original riddle rather than copying common examples.

    VARIETY REQUIREMENTS:

    - Explore different themes, objects, situations, and types of wordplay.
    - Avoid repeatedly using familiar riddles.
    - Avoid generating riddles similar to the recent examples below.

    RECENTLY GENERATED RIDDLES TO AVOID:
    {json.dumps(recent_puzzles, indent=2)}

    Return ONLY valid JSON with these fields:
    {{
        "category": "riddle",
        "difficulty": "{difficulty}",
        "question": "The complete riddle text",
        "content": {{
            "riddle_text": "The complete riddle text"
        }},
        "answer_type": "string",
        "correct_answer": "intended answer",
        "options": [],
        "accepted_answers": ["alternative answer"],
        "hints": [
            "First hint",
            "Second hint",
            "Third hint"
        ],
        "explanation": "Explain why this is the answer."
    }}

    The example is only a format reference. Do not copy it. 
    Do not include Markdown or additional text.
    
    """

    # Include validation feedback when correcting a failed generation
    if feedback:
        prompt += f"""
            PREVIOUS VALIDATION ERRORS: {feedback}

            Generate a new riddle that corrects these issues. 
        """

    return prompt


# In[16]:


# ==========================================
# RIDDLE GENERATOR
# ==========================================

def generate_riddle(difficulty, recent_puzzles=None, feedback=None):

    """
    Generates a riddle using Gemini.

    Parameters:
        difficulty (str): Requested difficulty.
        recent_puzzles (list, optional): Riddles to avoid repeating.
        feedback (str, optional): Validation feedback.

    Returns:
        dict: Raw riddle data returned by Gemini.
    """

    # Build the riddle generation prompt
    prompt = get_riddle_prompt(
        difficulty = difficulty,
        recent_puzzles = recent_puzzles,
        feedback = feedback
    )

    # Generate and parse the JSON response
    generated_data = generate_json_response(prompt)

    return generated_data


# # PUZZLE VALIDATION

# **10. COMMON VALIDATION**

# In[17]:


def validate_common_fields(puzzle):

    """
    Validates fields shared by all puzzle categories.

    Parameters:
        puzzle (dict): Puzzle object to validate.

    Returns:
        list: Validation error messages.
               Empty list means no common validation errors.
    """
    
    errors = []

    # All puzzles must contain these fields
    required_fields = [
        "puzzle_id",
        "category",
        "difficulty",
        "question",
        "content",
        "answer_type",
        "correct_answer",
        "options",
        "accepted_answers",
        "hints",
        "explanation",
        "source",
        "validation_status"
    ]

    # Check for missing fields before accessing them
    missing_fields = [
        field for field in required_fields
        if field not in puzzle
    ]

    if missing_fields:
        errors.extend([f"Missing required field: {field}" for field in missing_fields])

        # Stop here because further checks may require missing fields
        return errors

    # Category must be one of the supported categories
    if puzzle['category'] not in PUZZLE_CATEGORIES:
        errors.append('Invalid puzzle category')

    # Difficulty must be a supported level
    if puzzle['difficulty'] not in DIFFICULTY_LEVELS:
        errors.append('Invalid difficulty level.')

    # Question must be a supported level
    if not isinstance(puzzle['question'], str) or not puzzle['question'].strip():
        errors.append('Question must be a non-empty string')

    # Question must contain readable text
    if not isinstance(puzzle['question'], str) or not puzzle['question'].strip():
        errors.append('Question must be a non-empty string')

    # Content must be a dictionary
    if not isinstance(puzzle['content'], dict):
        errors.append('Content must be a dictionary')

    # Exactly 3 progressive hints are required
    hints = puzzle['hints']

    if not isinstance(hints, list) or len(hints) != MAX_HINTS:
        errors.append(f"Each puzzle must contain exactly {MAX_HINTS} hints")

    elif not all (isinstance(hint, str) and hint.strip() for hint in hints):
        errors.append('Every hint must be a non-empty string')

    # Options must be stored as a list
    if not isinstance(puzzle['options'], list):
        errors.append('Options must be a list')

    # Accepted answers must be stored as a list
    if not isinstance(puzzle['accepted_answers'], list):
        errors.append('Accepted answers must be a list')

    # Explanation must be readable text
    if not isinstance(puzzle['explanation'], str) or not puzzle['explanation'].strip():
        errors.append('Explanation must be a non-empty string')
    return errors
    


# **11. NUMBER PATTERN VALIDATION**

# In[18]:


def validate_number_pattern(puzzle):
    """
    Validates the structure and answer of a number pattern puzzle.

    Checks:
        - Required category-specific content.
        - Sequence structure and values.
        - Exactly one missing element.
        - Correct missing position.
        - Answer type and value.
        - Multiple-choice options.
        - Accepted answers.

    Parameters:
        puzzle (dict): Number pattern puzzle.

    Returns:
        list: Validation errors. An empty list means valid.
    """
    
    errors = []

    # Retrieve category-specific content safely
    content = puzzle.get("content")

    if not isinstance(content, dict):
        return ['Number pattern content must be a dictionary']

    # Required fields inside number pattern content
    required_content_fields = [
        "sequence",
        "missing_position",
        "pattern_type"
    ]

    # Check that all required content fields exist
    missing_fields = [
        field for field in required_content_fields
        if field not in content
    ]

    if missing_fields:
        errros.extend([f"Number pattern is missing: {field}" for field in missing_fields])
        return errors

    sequence = content['sequence']
    missing_position = content['missing_position']
    pattern_type = content['pattern_type']

    # ------------------------------------------
    # Sequence validation
    # ------------------------------------------

    if not isinstance(sequence, list):
        errors.append('Sequence must be a list.')

    else:
        # A sequence must have enough positions to form a pattern.
        if len(sequence) < 4:
            errors.append('Sequence must contain at least 4 positions')

        #Sequence values must be integers or None
        if not all(
            value is None or (isinstance(value, int) and not isinstance(value, bool))
            for value in sequence
        ):
            errors.append('Sequence values must be integers or None')

        # Exactly one position must be missing
        if sequence.count(None) != 1:
            errors.append('Sequence must contain exactly one missing value')

    # ------------------------------------------
    # Missing position validation
    # ------------------------------------------

    if not isinstance(missing_position, int) or isinstance(missing_position, bool):
        errors.append('Missing position must be an integer')

    elif isinstance(sequence, list):
        # The index must be within the sequence bounds
        if not (0 <= missing_position < len(sequence)):
            errors.append('Missing position is out of range')

        # The indicated position must contain None
        elif sequence[missing_position] is not None:
            errors.append('Specified missing position must contain None.')

    # ------------------------------------------
    # Pattern type validation
    # ------------------------------------------

    if not isinstance(pattern_type, str) or not pattern_type.strip():
        errors.append('Pattern type must be non-empty text')

    # ------------------------------------------
    # Answer validation
    # ------------------------------------------

    if puzzle.get('answer_type') != 'integer':
        errors.append('Number pattern answer type must be integer')

    answer = puzzle.get('correct_answer')

    # Booleans are technically subclasses of integers in Python, so we explicitly exclude them
    if not isinstance(answer, int) or isinstance(answer, bool):
        errors.append('Correct answer must be an integer')

    # ------------------------------------------
    # Options validation
    # ------------------------------------------

    options = puzzle.get('options')

    if not isinstance(options, list):
        errors.append('Options must be a list')

    else:
        if len(options) != 4:
            errors.append('Number pattern must have exactly 4 options')

        # Ensure the options are distinct
        if len(set(options)) != len(options):
            errors.append('Options must be unique')

        # The correct answer must be one of the choices
        if answer not in options:
            errors.append('Correcr answer must be included in the options')

        # Every option must be an integer
        if not all (isinstance(option, int) and not isinstance(option, bool)
                   for option in options):
            errors.append('All options must be integers')

    # ------------------------------------------
    # Accepted answers validation
    # ------------------------------------------

    accepted_answers = puzzle.get('accepted_answers')

    if accepted_answers != []:
        errors.append('Number pattern accepted_answers must be empty')

    return errors


# **12. RIDDLE VALIDATION**

# In[19]:


def validate_riddle(puzzle):

    """
    Validates the structure and answer of a riddle.

    Checks:
        - Required category-specific content.
        - Riddle text exists.
        - Answer is a non-empty string.
        - Accepted answers are valid strings.
        - No duplicate accepted answers.
        - Options are empty.
        - Common puzzle fields are valid.

    Parameters:
        puzzle (dict): Riddle puzzle.

    Returns:
        list: Validation errors. An empty list means valid.
    """

    errors = []

    # Retrieve category-specific content safely
    content = puzzle.get('content')

    if not isinstance(content, dict):
        return ['Riddle content must be dictionary']

    # ------------------------------------------
    # Riddle text validation
    # ------------------------------------------

    riddle_text = content.get('riddle_text')

    if not isinstance(riddle_text, str) or not riddle_text.strip():
        errors.append('Riddle text must be a non-empty string')

    # ------------------------------------------
    # Answer validation
    # ------------------------------------------  

    if puzzle.get("answer_type") != "string":
        errors.append('Riddle answer type must be string')

    answer = puzzle.get('correct_answer')

    if not isinstance(answer, str) or not answer.strip():
        errors.append('Correct answer must be a non-empty string')

    # ------------------------------------------
    # Accepted answers validation
    # ------------------------------------------

    accepted_answers = puzzle.get('accepted_answers')

    if not isinstance(accepted_answers, list):
        errors.append('Accepted answers must be a list')

    else:
        # Every alternative answer must be non-empty text
        if not all(isinstance(value, str) and value.strip() 
                  for value in accepted_answers):
            errors.append('Accepted answers must contain only non-empty strings')

        # Detect duplicates, ignoring case and whitespace
        normalized_answers = [
            value.strip().lower()
            for value in accepted_answers
            if isinstance(value, str)
        ]

        if len(normalized_answers) != len(set(normalized_answers)):
            errors.append('Accepted answers must not contain duplicates')

        # The correct answer should not be repeated among accepted answers
        if isinstance(answer, str):
            normalized_correct_answer = answer.strip().lower()

            if normalized_correct_answer in normalized_answers:
                errors.append('Accepted answers must not duplicate the correct answer')
        
    # ------------------------------------------
    # Options validation
    # ------------------------------------------

    options = puzzle.get('options')

    if options != []:
        errors.append('Riddle options must be empty')

    return errors


# **13. UNIFIED PUZZLE VALIDATION**

# In[20]:


def validate_puzzle(puzzle):
    """
    Validates a puzzle using common and category-specific rules.

    Parameters:
        puzzle (dict): Puzzle object to validate.

    Returns:
        list: All validation errors.
              An empty list means the puzzle is valid.
    """

    # Validate fields shared by all puzzle categories
    errors = validate_common_fields(puzzle)

    # If the category is missing or invalid, stop category validation
    category = puzzle.get('category')

    if category not in PUZZLE_CATEGORIES:
        return errors

    # Run category-specific validation
    if category == 'number_pattern':
        errors.extend(validate_number_pattern(puzzle))

    elif category == 'riddle':
        errors.extend(validate_riddle(puzzle))

    return errors


# # PUZZLE MANAGEMENT

# In[21]:


# Stored metadata about successfully generated puzzles
# Used to reduce repitition across future generation
generated_puzzle_history = []


# **14. CATEGORY-BASED PUZZLE GENERATION**

# In[22]:


def generate_puzzle_by_category(category, difficulty, feedback=None):

    """
    Routes puzzle generation to the appropriate generator.

    Parameters:
        category (str): Puzzle category.
        difficulty (str): Requested difficulty.
        feedback (str, optional): Validation feedback.

    Returns:
        dict: Raw generated puzzle data.
    """

    # Retrieve recent puzzle history to help avoid repitition
    recent_puzzles = [puzzle 
                     for puzzle in generated_puzzle_history[-RECENT_HISTORY_LIMIT:]
                     if puzzle['category'] == category]

    # Select the generator based on puzzle category
    if category == "number_pattern":
        return generate_number_pattern(
            difficulty = difficulty, 
            recent_puzzles = recent_puzzles,
            feedback = feedback
        )

    elif category == "riddle":
        return generate_riddle(
            difficulty = difficulty,
            recent_puzzles = recent_puzzles,
            feedback = feedback
        )

    else:
        raise ValueError(f"Unsupported puzzle category: {category}")


# **15. NORMALIZE GEMINI OUTPUT**

# In[23]:


def convert_to_puzzle(generated_data):

    """
    Converts raw Gemini output into the common puzzle structure.

    Missing fields receive safe defaults so the validator can
    report them as validation errors instead of causing KeyErrors.

    Parameters:
        generated_data (dict): Raw Gemini response.

    Returns:
        dict: Standardized puzzle object.
    """

    return create_puzzle(
        category=generated_data.get("category", ""),
        difficulty=generated_data.get("difficulty", ""),
        question=generated_data.get("question", ""),
        content=generated_data.get("content", {}),
        answer_type=generated_data.get("answer_type", ""),
        correct_answer=generated_data.get("correct_answer"),
        hints=generated_data.get("hints", []),
        explanation=generated_data.get("explanation", ""),
        options=generated_data.get("options", []),
        accepted_answers=generated_data.get("accepted_answers", []),
        source="ai"
    )


# **16. VALIDATED PUZZLE GENERATION PIPELINE**

# In[24]:


def generate_validated_puzzle(category, difficulty):
    """
    Generates a puzzle and retries until it passes validation
    or the maximum number of attempts is reached.

    Parameters:
        category (str): Puzzle category.
        difficulty (str): Requested difficulty.

    Returns:
        dict: A validated puzzle.

    Raises:
        RuntimeError: If no valid puzzle is generated.
    """

    feedback = None

    # Retry generation when validation fails.
    for attempt in range(1, MAX_GENERATION_ATTEMPTS + 1):

        print(
            f"Generation attempt {attempt}/"
            f"{MAX_GENERATION_ATTEMPTS}"
        )

        try:
            # Generate raw puzzle data.
            generated_data = generate_puzzle_by_category(
                category=category,
                difficulty=difficulty,
                feedback=feedback
            )

            # Normalize the raw response into our common structure.
            puzzle = convert_to_puzzle(generated_data)

            # Validate the standardized puzzle.
            errors = validate_puzzle(puzzle)

        except Exception as error:
            # Treat generation or conversion errors as retry feedback.
            errors = [f"Generation error: {str(error)}"]
            puzzle = None

        # ------------------------------------------
        # Successful generation
        # ------------------------------------------

        if not errors:
            puzzle["validation_status"] = "valid"

            print("Puzzle generated and validated successfully!")

            # Store compact metadata to reduce repetition.
            history_entry = {
                "puzzle_id": puzzle["puzzle_id"],
                "category": puzzle["category"],
                "difficulty": puzzle["difficulty"],
                "question": puzzle["question"],
                "content": puzzle["content"],
                "correct_answer": puzzle["correct_answer"]
            }

            generated_puzzle_history.append(history_entry)

            return puzzle

        # ------------------------------------------
        # Failed validation
        # ------------------------------------------

        print("Validation failed:")

        for error in errors:
            print("-", error)

        # Send validation errors back to Gemini on the next attempt.
        feedback = "\n".join(errors)

    # ------------------------------------------
    # All attempts exhausted
    # ------------------------------------------

    raise RuntimeError(
        f"Failed to generate a valid {category} puzzle "
        f"at {difficulty} difficulty after "
        f"{MAX_GENERATION_ATTEMPTS} attempts."
    )


# # GAME SESSION MANAGEMENT

# **17. GAME SESSION**
# 
# Each time a player starts playing:
# - A new session is created.
# - Difficulty starts at Easy.
# - The player has no previous performance history.
# - A category is selected randomly.
# - The session tracks progress.

# In[25]:


#defining game session

def create_game_session():

    """
    Create and initialize a new game session.

    Every new session starts at easy difficulty with zero score
    and no puzzles played.
    """

    session = {
        'session_id': str(uuid.uuid4()),
        'started_at': datetime.now(timezone.utc).isoformat(),
        'current_difficulty': STARTING_DIFFICULTY,
        
        'total_attempts': 0,
        'correct_answers': 0,
        'incorrect_answers': 0,

        'total_time': 0,
        'total_hints_used':0,

        'attempt_history': [],
        'puzzle_history': [],
        'adaptation_history': []
    }

    return session


# **18. CATEGORY SELECTION**
# 
# - Categories are selected randomly.
# - The same category won't appear twice consecutively.

# In[26]:


def select_random_category(session):
    """
    Randomly select a puzzle category, avoiding the category
    used in the previous puzzle.
    """

    previous_category = None

    # Get the category of the previous puzzle, if one exists.
    if session["puzzle_history"]:
        previous_category = session["puzzle_history"][-1]["category"]

    # Exclude the previous category from the available choices.
    available_categories = [
        category
        for category in PUZZLE_CATEGORIES
        if category != previous_category
    ]

    # Randomly select one of the remaining categories.
    selected_category = random.choice(available_categories)

    return selected_category


# **19. START NEXT ROUND**

# In[27]:


def start_next_round(session):

    """
    Select a category, generate a validated puzzle at the session's current difficulty,
    and record it in the session.
    """

    # Select a category while avoiding consecutive repetitions
    category = select_random_category(session)

    # Get the current difficulty from the session
    difficulty = session['current_difficulty']

    # Generate a puzzle and ensure it passes validation
    puzzle = generate_validated_puzzle(
        category = category,
        difficulty = difficulty
    )

    session['current_hints_used'] = 0

    # Record the puzzle in the session history
    session['puzzle_history'].append({
        'puzzle_id': puzzle['puzzle_id'],
        'category': category,
        'difficulty': difficulty,
        'question': puzzle['question'],
        'started_at': datetime.now(timezone.utc).isoformat()
    })

    return puzzle


# **20. RECORD ATTEMPTS**

# In[28]:


def record_attempt(
    session,
    puzzle,
    player_answer,
    is_correct,
    time_taken,
    attempts,
    hints_used
):
    """
    Record a player's attempt and update the session statistics.

    Stores individual attempt details in attempt_history and updates the overall session 
    performance metrics.
    """

    # Create a record containing the details of this attempt.
    attempt_record = {
        "attempt_id": str(uuid.uuid4()),
        "puzzle_id": puzzle['puzzle_id'],
        "category": puzzle['category'],
        "difficulty": puzzle['difficulty'],
        "player_answer": player_answer,
        "is_correct": is_correct,
        "time_taken": time_taken,
        "attempts": attempts,
        "hints_used": hints_used,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    #Store individual attempt
    session['attempt_history'].append(attempt_record)

    #Update overall session statistics
    session['total_attempts'] += 1
    session['total_time'] += time_taken
    session['total_hints_used'] += hints_used

    if is_correct:
        session['correct_answers'] += 1
    else:
        session['incorrect_answers'] += 1

    return attempt_record


# **21. RECORD PLAYER PERFORMANCE**

# In[29]:


def get_player_performance(session):

    """
    Calculate overall player performance for the current session.
    Returns accuracy, average completion time, and average hints used. 
    """
    
    total = session['total_attempts']
    correct = session['correct_answers']

    # Calculate overall accuracy
    accuracy = (correct/total) * 100 if total > 0 else 0

    # Calculate average time per completed attempt
    average_time = session['total_time'] / total if total > 0 else 0
    
    # Calculate average hints used per completed attempt
    average_hints = session['total_hints_used'] / total if total > 0 else 0
    
    return {
        "total_attempts": total,
        "correct_answers": correct,
        "incorrect_answers": session['incorrect_answers'],
        "accuracy_percentage": round(accuracy, 2),
        "average_time_seconds": round(average_time, 2),
        "average_hints_used": round(average_hints, 2)
    }


# **22. RETRIEVE RECENT PERFORMANCE**

# In[30]:


#track recent performance
def get_recent_performance(session, limit=5):

    """
    Calculate player performance over the most recent attempts.

    Args:
        session: Current game session
        limit: Maximum number of recent attempts to consider

    Returns:
        Recent attempt records and their accuracy percentage
    """

    # Get the most recent attempts
    recent_attempts = session['attempt_history'][-limit:]

    # Handle sessions with no recorded attempts
    if not recent_attempts:
        return{
            "attempts": [],
            "accuracy_percentage": 0
        }

    # Count the correct answers among recent attempts
    correct_count = sum(
        1 for attempt in recent_attempts
        if attempt['is_correct']
    )

    # Calculate accuracy based on the recent attempts
    accuracy = (correct_count / len(recent_attempts)) *100

    return {
        "attempts": recent_attempts,
        "accuracy_percentage": round(accuracy,2)
    }


# **23. RECORD COMPLETED PUZZLE**

# In[31]:


def record_completed_puzzle(
    session,
    puzzle,
    final_answer,
    is_correct,
    time_taken,
    attempts,
    hints_used
):

    """
    Update the existing puzzle history record with completion details
    """

    # Find the puzzle that was started in the current session
    puzzle_record = None

    for record in session['puzzle_history']:
        if record['puzzle_id'] == puzzle['puzzle_id']:
            puzzle_record = record
            break

    # Ensure the puzzle exists in the session history
    if puzzle_record is None:
        raise ValueError('Puzzle not found in session history')
        
    # Add the completed puzzle to the session history
    puzzle_record.update({
        "final_answer": final_answer,
        "is_correct": is_correct,
        "time_taken": time_taken,
        "attempts": attempts,
        "hints_used": hints_used,
        "completed_at": datetime.now(timezone.utc).isoformat()
    })
    
    return puzzle_record


# # ADAPTIVE DIFFICULTY

# **24. BUILD ADAPTATION CONTEXT**

# In[32]:


def build_adaptation_context(session, recent_limit=5):

    """
    Build a summary of the player's performance for AI-based difficulty adaptation.

    Parameters:
        session (dict): Current game session
        recent_limit (int): Number of recent completed puzzles to consider

    Returns:
        dict: Player performance context for the AI
    """

    # Get only puzzles that have been completed
    completed_puzzles = []

    for puzzle in session['puzzle_history']:
        if 'is_correct' in puzzle:
            completed_puzzles.append(puzzle)

    # Get the most recent completed puzzles
    recent_puzzles = completed_puzzles[-recent_limit:]

    # Calculate the overall performance
    total_completed = len(completed_puzzles)

    correct_count = sum(
        1 for puzzle in completed_puzzles
        if puzzle['is_correct']
    )

    accuracy = correct_count / total_completed * 100 if total_completed > 0 else 0

    # Calculate recent performance
    recent_correct = sum(
        1 for puzzle in recent_puzzles
        if puzzle['is_correct']
    )

    recent_accuracy = (
        recent_correct/len(recent_puzzles) * 100
        if recent_puzzles
        else 0
    )

    return{
        "current_difficulty": session['current_difficulty'],
        "total_puzzles_completed": total_completed,
        "overall_accuracy_percentage": round(accuracy, 2),
        "recent_accuracy_percentage": round(recent_accuracy, 2),
        "recent_puzzles": recent_puzzles
    }


# **25. GET ADAPTATION PROMPT**

# In[33]:


#adaptation prompt function
def get_adaptation_prompt(context):

    """
    Build the prompt for Gemini to recommend the next puzzle difficulty.

    Parameters:
        context (dict): Player performance data from build_adaptation_context()

    Returns:
        str: Prompt for Gemini
    """
    
    prompt = f"""
    You are the adaptive difficulty manager for Puzzle Pirates, an AI-powered brain puzzle game.
    Your job is to analyze player performance and recommend the difficulty of the next puzzle.

    Available difficulty levels:
    - easy
    - medium
    - hard

    Player performance data:
    {json.dumps(context, indent=2)}

    Decision guidelines:

    1. Consider both overall and recent performance.
    2. Consider correctness, completion time, attempts, and hints used from the recent puzzle records.
    3. Consistently strong performance may justify increasing difficulty.
    4. Repeated mistakes or substantial use of hints may justify decreasing difficulty.
    5. Mixed performance may justify maintaining current difficulty.
    6. Do not make a large jump without sufficient evidence.
    7. If the player has completed very few puzzles, be conservative.
    8. Only recommend one difficulty level above or below the current level.

    Return ONLY valid JSON in this exact format:

    {{
        "recommended_difficulty":"easy",
        "decision":"maintain",
        "reasoning": "Brief explanation of your decision"
    }}

    The decision must be one of:
    - increase
    - decrease
    - maintain

    The recommended difficulty must be:
    - easy
    - medium
    - hard.

    Do not include Markdown or additional text
    """

    return prompt


# **26. GET DIFFICULTY RECOMMENDATION**

# In[34]:


def get_ai_difficulty_recommendation(session):

    """
    Ask Gemini to recommend the difficulty for the next puzzle based on the player's session
    performance.

    Parameters:
        session (dict): Current game session

    Returns:
        dict: Validated difficulty recommendation from Gemini
    """

    # Build the player's performance context
    context = build_adaptation_context(session)

    # Create the prompt for Gemini
    prompt = get_adaptation_prompt(context)

    # Generate and parse Gemini's JSON response
    recommendation = generate_json_response(prompt)

    #Validate the AI response
    recommended_difficulty = recommendation.get("recommended_difficulty")

    if recommended_difficulty not in DIFFICULTY_LEVELS:
        raise ValueError("Gemini returned an invalid difficulty")

    decision = recommendation.get('decision')

    if decision not in ["increase", "decrease", "maintain"]:
        raise ValueWrror("Gemini returned an invalid decision")

    reasoning = recommendation.get('reasoning')
    
    if not isinstance(reasoning, str) or not reasoning.strip():
        raise ValueError("Gemini did not provide reasoning")

    return recommendation
    


# **27. UPDATE DIFFICULTY**

# In[35]:


def update_session_difficulty(session, recommendation):
    
    """
    Update the session's current difficulty and record the AI's adaptation decision.

    Parameters:
        session (dict): Current game session
        recommendation (dict): Validated recommendation from Gemini.

    Returns:
        dict: Record of the difficulty adaptation
    """
    
    previous_difficulty = session['current_difficulty']
    new_difficulty = recommendation['recommended_difficulty']
    decision = recommendation['decision']

    # Get the position of each difficulty level
    current_index = DIFFICULTY_LEVELS.index(previous_difficulty)
    new_index = DIFFICULTY_LEVELS.index(new_difficulty)

    # Check that the difficulty changes by no more than one level
    if abs(new_index - current_index) > 1:
        raise ValueError('Difficulty cannot change by more than one level')

    # CHeck that the decision matches the recommended difficulty
    if decision == 'increase' and new_index <= current_index:
        raise ValueError('An increase secision must raise the difficulty')

    elif decision == 'decrease' and new_index >= current_index:
        raise ValueError('A decrease decision must lower the difficulty')

    elif decision == 'maintain' and new_index != current_index:
        raise ValueError('A maintain decision must keep the same difficulty')

    # Update the session difficulty
    session['current_difficulty'] = new_difficulty

    # Record the adaptation decision
    adaptation_record = {
        "previous_difficulty": previous_difficulty,
        "new_difficulty": new_difficulty,
        "decision": recommendation['decision'],
        "reasoning": recommendation['reasoning'],
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    session['adaptation_history'].append(adaptation_record)

    return adaptation_record


# # AGENT TOOLS

# **28. CHECK ANSWERS**

# In[36]:


#checking answers

def normalize_text(answer):

    """
    Standardize a text answer before comparison.

    Converts the answer to lowercase and removes leading, trailing, and extra whitespace.

    Parameters:
        answer: Player's submitted answer

    Returns:
        str: Normalized answer, or an empty string if input is not text
    """
    
    if not isinstance(answer, str):
        return ""

    return " ".join(answer.strip().lower().split())

def check_answer(puzzle, player_answer):

    """
    Check whether the player's answer matches the puzzle's correct answer.

    Supports integer, string, and structured answer types.

    Parameters:
        puzzle (dict): Generated puzzle containing the correct answer
        player_answer: Answer submitted by the player

    Returns:
        dict: Answer evaluation containing correctness, feedback, submitted answer, and explanation
        when correct
    """
    
    answer_type = puzzle['answer_type']
    correct_answer = puzzle['correct_answer']

    is_correct = False

    # --------------------------------------------------
    # 1. Check integer answers (number pattern puzzles)
    # --------------------------------------------------
    if answer_type == 'integer':
        try:
            #Reject boolean valyes because bool is a subclass of int
            if isinstance(player_answer, bool):
                raise ValueError

            # Convert the submitted answer to an integer
            submitted_answer = int(player_answer)
            
            # Reject decimals and non-integer representations
            if str(player_answer).strip() not in [str(submitted_answer), f"+{submitted_answer}"]:
                raise ValueError

            # Compare the submitted integer with the correct answer
            is_correct = submitted_answer == correct_answer

        except(ValueError, TypeError):
            is_correct = False

    # --------------------------------------------------
    # 2. Check string answers (riddle puzzles)
    # --------------------------------------------------
    elif answer_type == 'string':

        # Normalize the player's answer
        normalized_answer = normalize_text(player_answer)

        # Include the corrext answer and accepted alternatives
        accepted_answers = [correct_answer] + puzzle.get('accepted_answers', [])

        # Normalize all valid answers before comparison
        normalized_accepted = [normalize_text(answer) for answer in accepted_answers
            if isinstance(answer, str)]

        is_correct = normalized_answer in normalized_accepted

    # --------------------------------------------------
    # 3. Check structured answers (reserved for future use)
    # --------------------------------------------------
    elif answer_type == 'structured':
        is_correct = player_answer == correct_answer

    # --------------------------------------------------
    # 4. Handle unsupported answer types
    # --------------------------------------------------
    else: 
        raise ValueError(f"Unsupported answer type: {answer_type}")

    # --------------------------------------------------
    # 5. Prepare the evaluation result
    # --------------------------------------------------
    result = {
        "is_correct": is_correct,
        "player_answer": player_answer,
        "feedback": (
            "Correct! Well done!"
            if is_correct
            else "Not quite. Try again!"
        ),
        "explanation": (
            puzzle["explanation"]
            if is_correct
            else None
        )
    }

    return result


# **29. HINTS**

# In[37]:


def provide_hint(puzzle, session):

    """
    Provide the next available hint for a puzzle.

    Parameters:
        puzzle (dict): Current puzzle containing the list of hints.
        session (dict): Current game session

    Returns:
        dict: Hint result containing the hint, updated hint count, and availability status
    """

    # Get the number of hints already used in this round
    hints_used = session['current_hints_used']
    
    # Get the available hints from the puzzle
    hints = puzzle['hints']

    # Check whether the player has reached the hint limit
    if hints_used >= MAX_HINTS:
        return{
            "hint": None,
            "hints_used": hints_used,
            "remaining_hints": 0,
            "message": "You have used all available hints"
        }

    # Get the next hint based on the number already used
    hint = hints[hints_used]

    # Update the number of hints used
    session['current_hints_used'] += 1
    session['total_hints_used'] += 1

    # Return the hint and updated hint information
    return {
        "hint": hint,
        "hints_used": session['current_hints_used'],
        "remaining_hints": MAX_HINTS - session['current_hints_used'],
        "message": "Here is your next hint!"
    }


# **30. EXPLAIN PUZZLE**

# In[38]:


def explain_puzzle(puzzle):
    """
    Return the explanation for a puzzle.

    Parameters:
        puzzle (dict): Current puzzle containing its explanation.

    Returns:
        dict: Explanation and a message.
    """

    explanation = puzzle.get("explanation")

    # Check whether an explanation is available
    if not isinstance(explanation, str) or not explanation.strip():
        return {
            "explanation": None,
            "message": "No explanation is available for this puzzle."
        }

    return {
        "explanation": explanation,
        "message": "Here is the puzzle explanation."
    }


# # MAIN FUNCTIONS

# In[39]:


def start_game():
    # Create a new game session
    session = create_game_session()

    # Generate the first puzzle
    current_puzzle = start_next_round(session)

    return session, current_puzzle


# In[46]:


def submit_player_answer(session, current_puzzle, player_answer, attempts=1):

    # Check the player's answer
    answer_result = check_answer(current_puzzle, player_answer)
    is_correct = answer_result["is_correct"]

    # Find when the current puzzle started
    puzzle_record = next(
        (
            record for record in session["puzzle_history"]
            if record["puzzle_id"] == current_puzzle["puzzle_id"]
        ),
        None
    )

    if puzzle_record is None:
        raise ValueError("Current puzzle was not found in session history.")

    # Calculate time taken
    started_at = datetime.fromisoformat(puzzle_record["started_at"])
    time_taken = (
        datetime.now(timezone.utc) - started_at
    ).total_seconds()

    # Get hints used in this round
    hints_used = session["current_hints_used"]

    # Record the attempt
    record_attempt(
        session,
        current_puzzle,
        player_answer,
        is_correct,
        time_taken,
        attempts,
        hints_used
    )

    # Mark the puzzle as completed
    record_completed_puzzle(
        session,
        current_puzzle,
        player_answer,
        is_correct,
        time_taken,
        attempts,
        hints_used
    )

    return {
        "is_correct": is_correct,
        "correct_answer": current_puzzle["correct_answer"],
        "message": "Correct answer!" if is_correct else "Not quite! Better luck next time.",
        "time_taken": round(time_taken, 2),
        "attempts": attempts,
        "hints_used": hints_used
    }


# In[41]:


def request_hint(session, current_puzzle):

    if current_puzzle is None:
        raise ValueError("There is no active puzzle.")

    hint_result = provide_hint(current_puzzle, session)

    return hint_result


# In[42]:


def finish_round(session, continue_game=True):

    # Get the player's performance
    performance = get_player_performance(session)

    # Get AI difficulty recommendation
    recommendation = get_ai_difficulty_recommendation(session)

    # Apply the recommendation
    adaptation = update_session_difficulty(
        session,
        recommendation
    )

    # Generate the next puzzle if the player wants to continue
    if continue_game:
        next_puzzle = start_next_round(session)
    else:
        next_puzzle = None

    return {
        "performance": performance,
        "adaptation": adaptation,
        "next_puzzle": next_puzzle,
        "game_over": not continue_game
    }


# In[45]:


def main():

    # Start a new game
    session, current_puzzle = start_game()

    print("\n🏴‍☠️ Welcome to Puzzle Pirates!")
    print("Solve puzzles, earn your progress, and challenge yourself!")

    while True:

        # Display the current puzzle
        print("\n" + "=" * 45)
        print(f"Category: {current_puzzle['category']}")
        print(f"Difficulty: {current_puzzle['difficulty']}")
        
        if current_puzzle["category"] == "number_pattern":
        
            sequence = current_puzzle["content"]["sequence"]
        
            # Replace the missing value with a blank
            display_sequence = [
                "_" if value is None else str(value)
                for value in sequence
            ]
        
            print(current_puzzle["question"])
            print("Sequence:", ", ".join(display_sequence))
        
        elif current_puzzle["category"] == "riddle":
        
            print(current_puzzle["question"])
        
        # Display options
        if current_puzzle["options"]:
            print("Options:", current_puzzle["options"])

        # Allow hints before submitting an answer
        while True:
            player_input = input(
                "\nEnter your answer (or type 'hint' for a hint): "
            ).strip()

            if player_input.lower() == "hint":
                hint_result = request_hint(session, current_puzzle)

                if hint_result["hint"]:
                    print("\nHint:", hint_result["hint"])
                    print("Hints remaining:", hint_result["remaining_hints"])
                else:
                    print(hint_result["message"])

            else:
                break

        # Submit the player's single answer
        result = submit_player_answer(
            session,
            current_puzzle,
            player_input
        )

        print("\n" + result["message"])
        print("Correct answer:", result["correct_answer"])
        print("Explanation:", current_puzzle["explanation"])
        print("Time taken:", result["time_taken"], "seconds")

        # Ask whether the player wants another puzzle
        choice = input("\nWould you like another puzzle? (yes/no): ").strip().lower()

        continue_game = choice in ["yes", "y"]

        # Finish the round and adapt difficulty
        round_result = finish_round(
            session,
            continue_game=continue_game
        )

        if not continue_game:
            print("\nThanks for playing Puzzle Pirates!")
            print("Final performance:", round_result["performance"])
            break

        # Move to the next puzzle
        current_puzzle = round_result["next_puzzle"]

        print(
            "\nYour next difficulty:",
            session["current_difficulty"]
        )


# In[47]:


if __name__ =="__main__":
    main()






