
import streamlit as st
import game_engine

st.set_page_config(
    page_title="Puzzle Pirates",
    page_icon="🏴‍☠️",
    layout="centered"
)

st.title("🏴‍☠️ Puzzle Pirates")
st.subheader("Welcome, puzzle explorer!")

st.write("Ready to test your puzzle-solving skills?")

# Initialize game state
if "session" not in st.session_state:
    st.session_state.session = None

if "current_puzzle" not in st.session_state:
    st.session_state.current_puzzle = None

# Start game
if st.button("Start Game"):
    session, puzzle = game_engine.start_game()

    st.session_state.session = session
    st.session_state.current_puzzle = puzzle


# Display current puzzle
if st.session_state.current_puzzle is not None:
    puzzle = st.session_state.current_puzzle

    st.success("Your game has started!")

    st.write("Category:", puzzle["category"].replace("_", " ").title())
    st.write("Difficulty:", puzzle["difficulty"].title())

    st.subheader("Your Puzzle")

    # Display number pattern content
    if puzzle["category"] == "number_pattern":
        st.write(puzzle["question"])

        sequence = puzzle["content"]["sequence"]
        display_sequence = [
            "?" if value is None else str(value)
            for value in sequence
        ]

        st.markdown("### " + "  →  ".join(display_sequence))

        st.write("Choose from the following options:")
        st.write(puzzle["options"])

    # Display riddle content
    elif puzzle["category"] == "riddle":
        st.write(puzzle["content"]["riddle_text"])

    # Answer submission
    if "answer_result" not in st.session_state:
        st.session_state.answer_result = None

    if st.session_state.answer_result is None:

        with st.form("answer_form"):
            player_answer = st.text_input("Your answer:")

            submitted = st.form_submit_button("Submit Answer")

            if submitted:
                if player_answer.strip():
                    result = game_engine.submit_player_answer(
                        st.session_state.session,
                        puzzle,
                        player_answer
                    )

                    st.session_state.answer_result = result
                    st.rerun()
                else:
                    st.warning("Please enter an answer.")

    # Display answer feedback
    if st.session_state.answer_result is not None:
        result = st.session_state.answer_result

        if result["is_correct"]:
            st.success(result["message"])
        else:
            st.error(result["message"])

        st.write("Correct answer:", result["correct_answer"])
        st.write("Explanation:", puzzle["explanation"])
        st.write("Time taken:", result["time_taken"], "seconds")

