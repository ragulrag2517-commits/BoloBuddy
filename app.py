from __future__ import annotations

import base64
import html
import json
from pathlib import Path

import streamlit as st

from database import (
    get_activity_history,
    get_activity_summary,
    get_contributions,
    get_offline_items,
    get_vocabulary,
    initialize_database,
    remove_offline_item,
    reject_translation,
    record_activity,
    save_offline_item,
    submit_translation,
    upsert_vocabulary,
)
from translator import translate_exact_match
from worksheet import create_worksheet_pdf, find_devanagari_font

ROOT = Path(__file__).parent
DATA_FILE = ROOT / "language_data.json"
DB_FILE = ROOT / "data" / "bolobuddy.sqlite3"

st.set_page_config(
    page_title="BoloBuddy | Speak • Learn • Play • Grow",
    page_icon="🌱",
    layout="wide",
    initial_sidebar_state="expanded",
)


def load_styles() -> None:
    css_path = ROOT / "assets" / "styles" / "custom.css"
    if css_path.exists():
        st.markdown(f"<style>{css_path.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)


def load_language_data() -> dict:
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


LANGUAGES = load_language_data()["languages"]
LANGUAGE_NAMES = {language["code"]: language["name"] for language in LANGUAGES}
LANGUAGE_LABELS = {language["name"]: language["code"] for language in LANGUAGES}


def speak_button(text: str, language_code: str) -> None:
    """Offer browser speech only; the selected device must have a matching voice."""
    lang_tag = {"hi": "hi-IN", "sat": "sat-IN", "hoc": "hoc-IN", "unr": "unr-IN"}.get(
        language_code, "en-IN"
    )
    safe_text = json.dumps(text, ensure_ascii=True).replace("</", "<\\/")
    safe_lang = json.dumps(lang_tag)
    st.html(
        f"""
        <button class="listen-button" type="button" onclick="
          const utterance = new SpeechSynthesisUtterance({safe_text});
          utterance.lang = {safe_lang};
          window.speechSynthesis.cancel();
          window.speechSynthesis.speak(utterance);
        ">🔊 Listen</button>
        <style>
          .listen-button {{
            border: 0; border-radius: 999px; padding: 10px 18px;
            background: #e8f4dc; color: #335a36; font-size: 15px;
            font-weight: 700; cursor: pointer;
          }}
          .listen-button:hover {{ background: #d7edc4; }}
        </style>
        """,
        unsafe_allow_javascript=True,
    )


def set_page(page: str) -> None:
    st.session_state["navigation"] = page


def language_selector(key: str = "target_language") -> str:
    labels = list(LANGUAGE_LABELS)
    default_label = LANGUAGE_NAMES.get(st.session_state.get(key, "hi"), "Hindi")
    selected = st.selectbox("Learning language", labels, index=labels.index(default_label), key=f"{key}_label")
    code = LANGUAGE_LABELS[selected]
    st.session_state[key] = code
    return code


def render_language_notice(code: str) -> None:
    if code != "hi":
        st.info(
            f"No approved {LANGUAGE_NAMES[code]} translations are included yet. "
            "This prototype will not guess or machine-translate tribal-language words. "
            "A native speaker can contribute a word in Teacher Corner for local review."
        )


def render_header(title: str, subtitle: str) -> None:
    st.markdown(f'<div class="page-heading"><h1>{title}</h1><p>{subtitle}</p></div>', unsafe_allow_html=True)


def render_home() -> None:
    summary = get_activity_summary(DB_FILE)
    st.markdown(
        f"""
        <section class="hero">
          <div class="hero-copy">
            <div class="eyebrow">YOUR FRIENDLY MOTHER TONGUE LEARNING COMPANION</div>
            <h1>Namaste, little explorer! <span>🌈</span></h1>
            <p>Every new word is a little adventure. What shall we discover today?</p>
            <div class="hero-stats"><span>⭐ {summary['stars']} stars</span>
            <span>🌱 {summary['activities']} activities</span></div>
          </div>
          <div class="hero-art" aria-label="A happy learning adventure">📚 🐘 🌼</div>
        </section>
        """,
        unsafe_allow_html=True,
    )
    st.markdown('<div class="section-title"><h2>Pick your next adventure</h2><span>Small steps, big discoveries ✨</span></div>', unsafe_allow_html=True)
    adventures = [
        ("📖", "Word Garden", "Discover everyday words", "Learn New Words", "mint-card"),
        ("🦋", "Picture Explorer", "Look, match and remember", "Picture Explorer", "peach-card"),
        ("🎯", "Quiz Safari", "Play a quick question game", "Fun Quiz", "lilac-card"),
        ("🪄", "Story Nook", "Read a little story together", "Story Time", "blue-card"),
        ("🗣️", "Talk & Learn", "Try a word with your voice", "Talk & Learn", "yellow-card"),
        ("✏️", "Make a Worksheet", "Create practice to take home", "Worksheets", "pink-card"),
    ]
    columns = st.columns(3)
    for index, (icon, name, description, page, color) in enumerate(adventures):
        with columns[index % 3]:
            st.markdown(
                f'<div class="adventure-card {color}"><div class="adventure-icon">{icon}</div>'
                f'<h3>{name}</h3><p>{description}</p></div>',
                unsafe_allow_html=True,
            )
            st.button("Let's go →", key=f"home_{index}", on_click=set_page, args=(page,), use_container_width=True)
    st.markdown('<div class="footer-note">Made for curious minds, kind teachers and growing communities 💛</div>', unsafe_allow_html=True)


def render_words() -> None:
    render_header("🌻 Word Garden", "Pick a category and grow your word collection.")
    code = language_selector()
    render_language_notice(code)
    words = get_vocabulary(DB_FILE, code)
    if not words:
        return
    categories = ["All"] + sorted({word["category"] for word in words})
    category = st.selectbox("Choose a word garden", categories)
    visible = words if category == "All" else [word for word in words if word["category"] == category]
    columns = st.columns(3)
    for index, word in enumerate(visible):
        with columns[index % 3]:
            st.markdown(
                f'<div class="word-card"><div class="word-emoji">{html.escape(word["emoji"])}</div>'
                f'<div class="word-native">{html.escape(word["translation"])}</div>'
                f'<div class="word-english">{html.escape(word["en"].title())}</div>'
                f'<span class="category-pill">{html.escape(word["category"])}</span></div>',
                unsafe_allow_html=True,
            )
            speak_button(word["translation"], code)
            st.button(
                "📥 Save for offline",
                key=f"save_word_{word['id']}_{code}",
                on_click=save_offline_item,
                args=(DB_FILE, f"word:{word['id']}:{code}", "word", word),
            )
    if code == "hi":
        st.caption("🔊 Listening uses speech synthesis available in your browser or device.")


def render_picture_explorer() -> None:
    render_header("🦋 Picture Explorer", "Tap a picture, discover its word, and listen together.")
    code = language_selector()
    render_language_notice(code)
    words = get_vocabulary(DB_FILE, code)
    if not words:
        return
    if "picture_revealed" not in st.session_state:
        st.session_state["picture_revealed"] = None
    mode = st.radio("Choose a picture activity", ["Explore pictures", "Match a word to its picture"], horizontal=True)
    if mode == "Match a word to its picture":
        if "picture_match_index" not in st.session_state:
            st.session_state["picture_match_index"] = 0
        match_index = st.session_state["picture_match_index"] % len(words)
        target = words[match_index]
        st.markdown(
            f'<div class="quiz-card"><h2>Find the picture for “{html.escape(target["translation"])}”</h2>'
            "<p>Tap the matching picture.</p></div>",
            unsafe_allow_html=True,
        )
        columns = st.columns(4)
        result_key = f"picture_match_result_{code}_{match_index}"
        for index, word in enumerate(words):
            with columns[index % 4]:
                if st.button(
                    word["emoji"],
                    key=f"picture_match_{code}_{match_index}_{word['id']}",
                    use_container_width=True,
                    disabled=result_key in st.session_state,
                ):
                    correct = word["id"] == target["id"]
                    st.session_state[result_key] = correct
                    record_activity(DB_FILE, "picture-match", int(correct), int(correct), target["id"])
                    st.rerun()
        if result_key in st.session_state:
            if st.session_state[result_key]:
                st.success("That's the one! You earned a star ⭐")
            else:
                st.info(f"Good try! The picture was {target['emoji']} {target['en']}.")
            if st.button("Next picture →", key=f"next_picture_{code}_{match_index}"):
                st.session_state["picture_match_index"] += 1
                st.session_state.pop(result_key, None)
                st.rerun()
        return

    st.markdown("### Which picture would you like to explore?")
    columns = st.columns(4)
    for index, word in enumerate(words):
        with columns[index % 4]:
            st.button(
                f"{word['emoji']}\n\nTap to explore",
                key=f"picture_{word['id']}_{code}",
                use_container_width=True,
                on_click=lambda word_id=word["id"]: st.session_state.update(picture_revealed=word_id),
            )
    selected = next((word for word in words if word["id"] == st.session_state["picture_revealed"]), None)
    if selected:
        st.markdown(
            f'<div class="reveal-card"><div class="word-emoji">{html.escape(selected["emoji"])}</div>'
            f'<h2>{html.escape(selected["translation"])}</h2>'
            f'<p>In English, this is <strong>{html.escape(selected["en"])}</strong>.</p></div>',
            unsafe_allow_html=True,
        )
        speak_button(selected["translation"], code)
        st.button(
            "📥 Save this picture word",
            key=f"save_picture_{selected['id']}_{code}",
            on_click=save_offline_item,
            args=(DB_FILE, f"word:{selected['id']}:{code}", "word", selected),
        )


def render_quiz() -> None:
    render_header("🎯 Quiz Safari", "A tiny quiz is a big chance to shine. Get one right to earn a star!")
    code = language_selector()
    render_language_notice(code)
    words = get_vocabulary(DB_FILE, code)
    if len(words) < 2:
        st.warning("Add at least two approved words in this language before playing the quiz.")
        return

    if "quiz_index" not in st.session_state:
        st.session_state["quiz_index"] = 0
    index = st.session_state["quiz_index"] % len(words)
    question_word = words[index]
    options = [question_word["translation"]]
    options.extend(word["translation"] for word in words if word["id"] != question_word["id"])
    options = options[: min(4, len(options))]
    st.markdown(
        f'<div class="quiz-card"><div class="quiz-picture">{html.escape(question_word["emoji"])}</div>'
        f'<h2>Which word means “{html.escape(question_word["en"])}”?</h2>'
        "<p>Choose your answer below.</p></div>",
        unsafe_allow_html=True,
    )
    previous_result = st.session_state.get("quiz_result")
    answered = bool(previous_result and previous_result["index"] == index and previous_result["code"] == code)
    answer = st.radio("Your answer", options, key=f"quiz_answer_{code}_{index}", horizontal=True, disabled=answered)
    if st.button(
        "Check my answer ✨",
        type="primary",
        key=f"check_quiz_{code}_{index}",
        disabled=answered,
    ):
        is_correct = answer == question_word["translation"]
        st.session_state["quiz_result"] = {"index": index, "code": code, "correct": is_correct}
        record_activity(DB_FILE, "quiz", int(is_correct), int(is_correct), question_word["id"])
    result = st.session_state.get("quiz_result")
    if result and result["index"] == index and result["code"] == code:
        if result["correct"]:
            st.success("Wonderful! You found the right word. ⭐ One star for you!")
        else:
            st.info(f"Nice try! The answer is **{question_word['translation']}**. Keep exploring!")
        if st.button("Next question →", key=f"next_quiz_{code}_{index}"):
            st.session_state["quiz_index"] += 1
            st.session_state.pop("quiz_result", None)
            st.rerun()


def render_stories() -> None:
    render_header("🪄 Story Nook", "A short story, a new word, and a little question to think about.")
    code = language_selector()
    render_language_notice(code)
    stories = load_language_data()["stories"]
    available = [story for story in stories if story["language"] == code]
    if not available:
        return
    for story in available:
        st.markdown(
            f'<div class="story-card"><div class="story-art">{html.escape(story["illustration"])}</div>'
            f'<div><span class="category-pill">{html.escape(story["topic"])}</span>'
            f'<h2>{html.escape(story["title"])}</h2><p class="story-text">{html.escape(story["text"])}</p>'
            f'<p class="story-moral">{html.escape(story["moral"])}</p></div></div>',
            unsafe_allow_html=True,
        )
        speak_button(story["text"], code)
        st.button(
            "📥 Save this story offline",
            key=f"save_story_{story['id']}",
            on_click=save_offline_item,
            args=(DB_FILE, f"story:{story['id']}", "story", story),
        )
        st.markdown(f"**Think about it:** {story['question']}")
        result_key = f"story_result_{story['id']}"
        answered = result_key in st.session_state
        answer = st.radio(
            story["question"],
            story["choices"],
            key=f"story_answer_{story['id']}",
            label_visibility="collapsed",
            disabled=answered,
        )
        if st.button("Check story answer", key=f"story_check_{story['id']}", disabled=answered):
            correct = answer == story["answer"]
            record_activity(DB_FILE, "story", int(correct), int(correct), story["id"])
            st.session_state[result_key] = correct
        if result_key in st.session_state:
            if st.session_state[result_key]:
                st.success("That's right! You earned a story star ⭐")
            else:
                st.info(f"Good thinking! Here's one more clue: {story['answer']}")


def render_talk() -> None:
    render_header("🗣️ Talk & Learn", "Look up a saved word, then listen with your device's speech voice.")
    code = language_selector()
    render_language_notice(code)
    input_label = (
        "Type one English or Hindi vocabulary word"
        if code == "hi"
        else f"Type one English, Hindi, or approved {LANGUAGE_NAMES[code]} word"
    )
    phrase = st.text_input(input_label, placeholder="For example: dog or कुत्ता")
    if st.button("Find this word 🔎", type="primary"):
        result = translate_exact_match(phrase, get_vocabulary(DB_FILE, code))
        st.session_state["talk_result"] = result
    result = st.session_state.get("talk_result")
    if result:
        if result["translation"] is None:
            st.warning(result["message"])
        else:
            st.markdown(
                f'<div class="reveal-card"><div class="word-emoji">{html.escape(result["emoji"])}</div>'
                f'<h2>{html.escape(result["source"])} → {html.escape(result["translation"])}</h2>'
                f'<p>Exact match from the local approved word list ({html.escape(result["direction"])}).</p></div>',
                unsafe_allow_html=True,
            )
            speak_button(result["translation"], code)
    st.divider()
    st.markdown("#### 🎙️ About voice input")
    st.info(
        "This prototype does not transcribe microphone recordings or translate arbitrary speech. "
        "Use the word lookup above for exact matches. Speech playback depends on voices installed in your browser or device."
    )
    audio = st.audio_input("Optional: record a pronunciation to listen back")
    if audio:
        st.audio(audio)
        st.caption("Your recording is played in this session. It is not transcribed.")
        st.button(
            "📥 Save this recording offline",
            key="save_voice_recording",
            on_click=save_offline_item,
            args=(
                DB_FILE,
                f"audio:{audio.name}",
                "audio",
                {
                    "name": audio.name,
                    "mime_type": audio.type or "audio/wav",
                    "base64": base64.b64encode(audio.getvalue()).decode("ascii"),
                },
            ),
        )


def render_worksheets() -> None:
    render_header("✏️ Worksheet Workshop", "Make a simple take-home activity for your classroom.")
    code = language_selector()
    render_language_notice(code)
    grades = ["Class 1", "Class 2", "Class 3"]
    grade = st.selectbox("Class", grades)
    subject = st.selectbox("Subject", ["Language", "Foundational numeracy"])
    topic = st.selectbox("Topic", ["Everyday words", "Animals", "Fruits", "Colours", "Numbers"])
    words = get_vocabulary(DB_FILE, code)
    if topic != "Everyday words":
        words = [word for word in words if word["category"] == topic]
    if not words:
        st.warning("No approved words are available for this worksheet topic and language yet.")
    elif any(not word["translation"].isascii() for word in words) and find_devanagari_font() is None:
        st.warning(
            "No Devanagari font was found on this computer. The PDF leaves Hindi/local-script answer choices blank "
            "rather than producing missing glyphs; the language words still appear in the app."
        )
    st.caption("The worksheet includes a word-matching activity and a count-and-write activity.")
    if st.button("Create my worksheet 📄", type="primary", disabled=not words):
        try:
            pdf_data = create_worksheet_pdf(words, grade, subject, topic, LANGUAGE_NAMES[code])
        except (OSError, ValueError, RuntimeError) as error:
            st.error(f"Could not create the worksheet: {error}")
        else:
            st.session_state["worksheet_pdf"] = pdf_data
            record_activity(DB_FILE, "worksheet", 0, 0, f"{grade}:{subject}:{topic}")
            st.success("Your worksheet is ready!")
    if st.session_state.get("worksheet_pdf"):
        st.button(
            "📦 Save worksheet offline",
            key="save_worksheet_offline",
            on_click=save_offline_item,
            args=(
                DB_FILE,
                "worksheet:latest",
                "worksheet",
                {
                    "name": f"BoloBuddy {grade} worksheet.pdf",
                    "base64": base64.b64encode(st.session_state["worksheet_pdf"]).decode("ascii"),
                    "mime_type": "application/pdf",
                },
            ),
        )
        st.download_button(
            "⬇️ Download worksheet PDF",
            data=st.session_state["worksheet_pdf"],
            file_name=f"bolobuddy-{grade.lower().replace(' ', '-')}.pdf",
            mime="application/pdf",
        )
    st.caption(
        "Foundational practice is inspired by NIPUN Bharat's focus on early literacy and numeracy. "
        "This is a prototype worksheet, not an official NIPUN Bharat assessment."
    )


def render_progress() -> None:
    render_header("🏅 My Learning Trail", "Every practice session helps your learning garden grow.")
    summary = get_activity_summary(DB_FILE)
    col1, col2, col3 = st.columns(3)
    col1.metric("⭐ Stars earned", summary["stars"])
    col2.metric("🌱 Activities", summary["activities"])
    col3.metric("🎯 Correct answers", summary["correct"])
    st.progress(min(summary["stars"] / 10, 1.0), text=f"{summary['stars']} / 10 stars on the way to your next badge!")
    history = get_activity_history(DB_FILE)
    completed_stories = sum(activity["activity_type"] == "story" for activity in history)
    if completed_stories:
        st.markdown(f"📚 **Stories completed:** {completed_stories}")
    if summary["activities"] == 0:
        st.info("Your trail is ready! Try a word, story or quiz to earn your first star.")
    else:
        st.success("You're growing every time you practise. Keep up your wonderful work! 🌼")


def render_teacher_corner() -> None:
    render_header("🧑‍🏫 Teacher Corner", "Grow the local word garden together—with careful community review.")
    with st.expander("➕ Add a new vocabulary word", expanded=False):
        with st.form("new_vocabulary_form"):
            english = st.text_input("English word")
            hindi = st.text_input("Hindi word (optional)")
            category = st.selectbox("Category", ["Animals", "Fruits", "Colours", "Numbers", "Objects", "People", "Nature"])
            emoji = st.text_input("Picture symbol (emoji)", value="🌱", max_chars=8)
            submitted = st.form_submit_button("Add word")
            if submitted:
                if not english.strip():
                    st.error("Please add an English word.")
                else:
                    try:
                        upsert_vocabulary(DB_FILE, english, hindi, category, emoji, DATA_FILE)
                    except ValueError as error:
                        st.error(str(error))
                    else:
                        st.success("Word added to the local vocabulary garden.")
                        st.rerun()

    st.markdown("### 🌿 Contribute a community translation")
    st.caption(
        "Contributions stay pending and are not shown to children as translations until reviewed. "
        "The prototype stores data locally and does not verify contributor identities."
    )
    with st.form("translation_contribution_form"):
        words = get_vocabulary(DB_FILE, "hi")
        word_options = {f"{word['en'].title()} — {word['translation']}": word["id"] for word in words}
        selected_word = st.selectbox("Vocabulary word", list(word_options) or ["No words yet"])
        target = st.selectbox(
            "Language",
            ["Santhali", "Ho", "Mundari"],
            key="contribution_language",
        )
        translated = st.text_input("Suggested translation")
        contributor = st.text_input("Contributor name or community")
        notes = st.text_input("Pronunciation or context (optional)")
        submit_contribution = st.form_submit_button("Submit for local review")
        if submit_contribution:
            if not words or not translated.strip() or not contributor.strip():
                st.error("Choose a word and provide a suggested translation and contributor name.")
            else:
                language_code = LANGUAGE_LABELS[target]
                submit_translation(
                    DB_FILE,
                    word_options[selected_word],
                    language_code,
                    translated.strip(),
                    contributor.strip(),
                    notes.strip(),
                )
                st.success("Saved as pending. It is not yet available as an approved translation.")

    st.markdown("### 🔎 Local review queue")
    pending = get_contributions(DB_FILE, status="pending")
    if not pending:
        st.info("No translations are waiting for review.")
    for contribution in pending:
        with st.container(border=True):
            st.markdown(
                f"**{contribution['english'].title()}** · {LANGUAGE_NAMES[contribution['language_code']]}  \n"
                f"Suggestion: **{contribution['translation']}** · Contributor: {contribution['contributor']}"
            )
            if contribution["notes"]:
                st.caption(contribution["notes"])
            with st.form(f"review_{contribution['id']}"):
                reviewer = st.text_input("Reviewer name", key=f"reviewer_{contribution['id']}")
                source = st.text_input(
                    "Community/source reference",
                    key=f"source_{contribution['id']}",
                    placeholder="For example, named language group, locality, or review session",
                )
                native_confirm = st.checkbox(
                    "I am a native speaker or have completed a native-speaker review",
                    key=f"native_{contribution['id']}",
                )
                approve = st.form_submit_button("Approve translation")
                reject = st.form_submit_button("Reject suggestion")
                if approve:
                    if not reviewer.strip() or not source.strip() or not native_confirm:
                        st.error("Approval needs a reviewer, a source reference, and native-speaker review confirmation.")
                    else:
                        approve_translation(
                            DB_FILE,
                            contribution["id"],
                            reviewer.strip(),
                            source.strip(),
                            native_speaker_reviewed=native_confirm,
                            data_path=DATA_FILE,
                        )
                        st.success("Approved locally and added to the language JSON.")
                        st.rerun()
                if reject:
                    reject_translation(DB_FILE, contribution["id"], reviewer.strip() or "Local reviewer")
                    st.info("Suggestion rejected in the local review queue.")
                    st.rerun()

    st.markdown("### 📚 Classroom notes")
    st.markdown(
        "- Invite a local speaker to review pronunciation, meaning and context before approval.\n"
        "- Keep learner-facing words short and familiar; context can change the best translation.\n"
        "- Worksheet activities are practice aids, not official assessments."
    )


def render_offline_box() -> None:
    render_header("📦 Offline Learning Box", "Keep useful words close by on this computer.")
    st.info(
        "Saved items are stored in the local SQLite database. They remain available while this local app is running "
        "without internet; this prototype does not install a browser service worker or sync between devices."
    )
    items = get_offline_items(DB_FILE)
    if not items:
        st.markdown("### Your box is waiting for its first word")
        st.caption("Use “Save for offline” in Word Garden or Picture Explorer to add approved words.")
        return
    for item in items:
        content = item["content"]
        title = content.get(
            "translation",
            content.get("title", content.get("name", content.get("en", item["key"]))),
        )
        label = f"{content.get('emoji', '📘')} **{title}**"
        with st.container(border=True):
            st.markdown(f"{label} · {content.get('en', '')}")
            if item["type"] == "story":
                st.caption(content.get("text", ""))
            elif item["type"] == "audio" and content.get("base64"):
                st.audio(base64.b64decode(content["base64"]), mime=content.get("mime_type", "audio/wav"))
            elif item["type"] == "worksheet" and content.get("base64"):
                st.download_button(
                    "⬇️ Download saved worksheet",
                    data=base64.b64decode(content["base64"]),
                    file_name=content.get("name", "bolobuddy-worksheet.pdf"),
                    mime=content.get("mime_type", "application/pdf"),
                    key=f"download_saved_{item['key']}",
                )
            st.caption(f"Saved {item['saved_at'][:10]}")
            st.button(
                "Remove from box",
                key=f"remove_{item['key']}",
                on_click=remove_offline_item,
                args=(DB_FILE, item["key"]),
            )


PAGES = {
    "Welcome Home": render_home,
    "Learn New Words": render_words,
    "Picture Explorer": render_picture_explorer,
    "Fun Quiz": render_quiz,
    "Story Time": render_stories,
    "Talk & Learn": render_talk,
    "Worksheets": render_worksheets,
    "My Progress": render_progress,
    "Teacher Corner": render_teacher_corner,
    "Offline Box": render_offline_box,
}


def main() -> None:
    initialize_database(DB_FILE, DATA_FILE)
    load_styles()
    with st.sidebar:
        st.markdown('<div class="brand-mark">🌱 <strong>BoloBuddy</strong></div>', unsafe_allow_html=True)
        st.caption("Speak • Learn • Play • Grow")
        st.divider()
        pages = list(PAGES)
        current = st.session_state.get("navigation", pages[0])
        if current not in pages:
            current = pages[0]
        selected = st.radio("Choose your adventure", pages, index=pages.index(current), key="navigation")
        st.divider()
        summary = get_activity_summary(DB_FILE)
        st.markdown(f"### ⭐ {summary['stars']} learning stars")
        st.caption("Keep exploring—you are doing great!")
        st.markdown(
            '<div class="sidebar-note">🌼 Words grow stronger when families and teachers learn together.</div>',
            unsafe_allow_html=True,
        )
    PAGES[selected]()


if __name__ == "__main__":
    main()
