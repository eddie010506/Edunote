from flask import Flask, render_template, request, jsonify, redirect, url_for, send_from_directory
import os
import json
from datetime import datetime
import google.generativeai as genai
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
import re
import html

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['INDEX_UPLOAD_FOLDER'] = 'uploads/indices'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Ensure upload directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['INDEX_UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('data', exist_ok=True)

# Configure Gemini AI
# You'll need to set your API key as an environment variable: GOOGLE_API_KEY
api_key = os.getenv('GOOGLE_API_KEY')
if not api_key:
    print("WARNING: GOOGLE_API_KEY not found in environment variables!")
    print("Please create a .env file with your API key:")
    print("GOOGLE_API_KEY=your_api_key_here")
else:
    print(f"API Key loaded: {api_key[:10]}..." if len(api_key) > 10 else "API Key loaded")

if api_key:
    genai.configure(api_key=api_key)
    # Use the correct model name for Gemini
    model = genai.GenerativeModel('gemini-1.5-flash')
    print("✅ Gemini model configured successfully")
else:
    model = None
    print("❌ No API key provided - AI analysis will be disabled")

# Data storage (in production, use a proper database)
NOTES_DATA_FILE = 'data/notes.json'
SUBJECTS_DATA_FILE = 'data/subjects.json'
INDICES_DATA_FILE = 'data/indices.json'

def load_data(filename, default=None):
    """Load data from JSON file"""
    try:
        with open(filename, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return default if default is not None else {}

def save_data(filename, data):
    """Save data to JSON file"""
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2)

def clean_html_tags(text):
    """Clean up HTML tags and convert to readable format"""
    if not text or not isinstance(text, str):
        return text
    
    # Convert HTML entities first
    text = html.unescape(text)
    
    # Remove any existing HTML tags completely first
    text = re.sub(r'<[^>]+>', '', text)
    
    # Handle mathematical notation - convert to proper format
    # Handle ^ notation for superscripts (only in mathematical contexts)
    text = re.sub(r'(\w)\^(\d+)', r'\1<sup>\2</sup>', text)
    text = re.sub(r'(\w)\^([a-zA-Z])', r'\1<sup>\2</sup>', text)
    
    # Handle _ notation for subscripts (only in mathematical contexts)
    text = re.sub(r'(\w)_(\d+)', r'\1<sub>\2</sub>', text)
    text = re.sub(r'(\w)_([a-zA-Z])', r'\1<sub>\2</sub>', text)
    
    # Handle special mathematical symbols
    text = re.sub(r'∫', '∫', text)  # Integral symbol
    text = re.sub(r'∬', '∬', text)  # Double integral symbol
    
    # Clean up multiple spaces and newlines
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text

def clean_ai_analysis(analysis):
    """Clean up HTML tags in AI analysis data"""
    if not analysis:
        return analysis
    
    # Clean important points
    if 'important_points' in analysis:
        for point in analysis['important_points']:
            if 'text' in point:
                point['text'] = clean_html_tags(point['text'])
            if 'explanation' in point:
                point['explanation'] = clean_html_tags(point['explanation'])
    
    # Clean other text fields
    text_fields = ['key_topics', 'important_equations', 'highlights', 'test_questions', 'related_links']
    for field in text_fields:
        if field in analysis and isinstance(analysis[field], list):
            analysis[field] = [clean_html_tags(item) for item in analysis[field]]
        elif field in analysis:
            analysis[field] = clean_html_tags(analysis[field])
    
    # Clean index relevance
    if 'index_relevance' in analysis:
        analysis['index_relevance'] = clean_html_tags(analysis['index_relevance'])
    
    return analysis

@app.route('/')
def home():
    """Home page displaying subject folders"""
    subjects = load_data(SUBJECTS_DATA_FILE, {})
    return render_template('index.html', subjects=subjects)

@app.route('/manage')
def manage():
    """Management page for subjects and classes"""
    subjects = load_data(SUBJECTS_DATA_FILE, {})
    return render_template('manage.html', subjects=subjects)

@app.route('/api/subject', methods=['POST'])
def create_subject():
    """Create a new subject"""
    data = request.get_json()
    subject_name = data.get('name')
    
    if not subject_name:
        return jsonify({'error': 'Subject name required'}), 400
    
    subjects = load_data(SUBJECTS_DATA_FILE, {})
    if subject_name in subjects:
        return jsonify({'error': 'Subject already exists'}), 400
    
    subjects[subject_name] = {
        'name': subject_name,
        'classes': {},
        'created_date': datetime.now().isoformat()
    }
    
    save_data(SUBJECTS_DATA_FILE, subjects)
    return jsonify({'success': True, 'subject': subjects[subject_name]})

@app.route('/api/subject/<subject_name>/class', methods=['POST'])
def create_class(subject_name):
    """Create a new class within a subject"""
    data = request.get_json()
    class_name = data.get('name')
    
    if not class_name:
        return jsonify({'error': 'Class name required'}), 400
    
    subjects = load_data(SUBJECTS_DATA_FILE, {})
    if subject_name not in subjects:
        return jsonify({'error': 'Subject not found'}), 404
    
    if class_name in subjects[subject_name]['classes']:
        return jsonify({'error': 'Class already exists'}), 400
    
    subjects[subject_name]['classes'][class_name] = {
        'name': class_name,
        'indices': {},
        'note_count': 0,
        'created_date': datetime.now().isoformat()
    }
    
    save_data(SUBJECTS_DATA_FILE, subjects)
    return jsonify({'success': True, 'class': subjects[subject_name]['classes'][class_name]})

@app.route('/upload-index', methods=['POST'])
def upload_index():
    """Upload textbook index for a class"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    subject = request.form.get('subject')
    class_name = request.form.get('class_name')
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not subject or not class_name:
        return jsonify({'error': 'Subject and class name required'}), 400
    
    # Save uploaded index file
    filename = secure_filename(file.filename)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_{filename}"
    filepath = os.path.join(app.config['INDEX_UPLOAD_FOLDER'], filename)
    file.save(filepath)
    
    # Read and parse index content
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except:
        with open(filepath, 'r', encoding='latin-1') as f:
            content = f.read()
    
    # Parse index to extract chapters/sections
    index_structure = parse_textbook_index(content)
    
    # Save index data
    indices = load_data(INDICES_DATA_FILE, {})
    if subject not in indices:
        indices[subject] = {}
    if class_name not in indices[subject]:
        indices[subject][class_name] = {}
    
    indices[subject][class_name] = {
        'filename': filename,
        'original_name': file.filename,
        'content': content,
        'structure': index_structure,
        'upload_date': datetime.now().isoformat()
    }
    
    save_data(INDICES_DATA_FILE, indices)
    
    return jsonify({'success': True, 'structure': index_structure})

def parse_textbook_index(content):
    """Parse textbook index content to extract chapters and sections"""
    lines = content.split('\n')
    structure = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Look for patterns like "Chapter 1: Introduction" or "1.1 Basic Concepts"
        import re
        
        # Chapter pattern
        chapter_match = re.match(r'^chapter\s+(\d+)[:.]?\s*(.+)$', line.lower())
        if chapter_match:
            structure.append({
                'type': 'chapter',
                'number': chapter_match.group(1),
                'title': chapter_match.group(2).strip(),
                'level': 1
            })
            continue
            
        # Section pattern (1.1, 1.2, etc.)
        section_match = re.match(r'^(\d+\.\d+)[:.]?\s*(.+)$', line)
        if section_match:
            structure.append({
                'type': 'section',
                'number': section_match.group(1),
                'title': section_match.group(2).strip(),
                'level': 2
            })
            continue
            
        # Subsection pattern (1.1.1, 1.1.2, etc.)
        subsection_match = re.match(r'^(\d+\.\d+\.\d+)[:.]?\s*(.+)$', line)
        if subsection_match:
            structure.append({
                'type': 'subsection',
                'number': subsection_match.group(1),
                'title': subsection_match.group(2).strip(),
                'level': 3
            })
            continue
            
        # If no pattern matches, treat as a general topic
        if len(line) > 3:  # Skip very short lines
            structure.append({
                'type': 'topic',
                'title': line,
                'level': 0
            })
    
    return structure

@app.route('/subject/<subject_name>')
def subject_page(subject_name):
    """Display classes within a subject"""
    subjects = load_data(SUBJECTS_DATA_FILE, {})
    if subject_name not in subjects:
        return "Subject not found", 404
    
    classes = subjects[subject_name].get('classes', {})
    return render_template('subject.html', subject_name=subject_name, classes=classes)

@app.route('/class/<subject_name>/<class_name>')
def class_page(subject_name, class_name):
    """Display indices within a class"""
    indices = load_data(INDICES_DATA_FILE, {})
    notes_data = load_data(NOTES_DATA_FILE, {})
    class_indices = indices.get(subject_name, {}).get(class_name, {})
    class_notes = notes_data.get(subject_name, {}).get(class_name, {})
    
    # Clean AI analysis in class notes
    if class_notes:
        for index_key, index_notes in class_notes.items():
            for note in index_notes:
                if 'ai_analysis' in note:
                    note['ai_analysis'] = clean_ai_analysis(note['ai_analysis'])
    
    # Add note counts to each index
    if class_indices and 'structure' in class_indices:
        for item in class_indices['structure']:
            index_key = item.get('number', item.get('title', '').lower().replace(' ', '_'))
            note_count = len(class_notes.get(index_key, []))
            item['note_count'] = note_count
    
    return render_template('class.html', 
                         subject_name=subject_name, 
                         class_name=class_name, 
                         indices=class_indices,
                         class_notes=class_notes)

@app.route('/index/<subject_name>/<class_name>/<index_key>')
def index_page(subject_name, class_name, index_key):
    """Display notes within a specific index"""
    notes_data = load_data(NOTES_DATA_FILE, {})
    index_notes = notes_data.get(subject_name, {}).get(class_name, {}).get(index_key, [])
    
    # Get index structure for display
    indices = load_data(INDICES_DATA_FILE, {})
    index_info = None
    if subject_name in indices and class_name in indices[subject_name]:
        index_structure = indices[subject_name][class_name].get('structure', [])
        for item in index_structure:
            if item.get('number') == index_key or item.get('title', '').lower().replace(' ', '_') == index_key:
                index_info = item
                break
    
    # Create summary note if it doesn't exist
    summary_note = create_summary_note(index_notes)
    
    return render_template('index_notes.html', 
                         subject_name=subject_name, 
                         class_name=class_name,
                         index_key=index_key,
                         index_info=index_info,
                         notes=index_notes,
                         summary_note=summary_note)

@app.route('/upload', methods=['POST'])
def upload_note():
    """Handle note upload and AI evaluation"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    subject = request.form.get('subject')
    class_name = request.form.get('class_name')
    index_key = request.form.get('index_key')
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not subject or not class_name:
        return jsonify({'error': 'Subject and class name required'}), 400
    
    # Save uploaded file
    filename = secure_filename(file.filename)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_{filename}"
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)
    
    # Process with Gemini AI directly using the file
    ai_analysis = analyze_file_with_ai(filepath, filename, subject, class_name, index_key)
    
    # Clean up HTML tags in AI analysis
    ai_analysis = clean_ai_analysis(ai_analysis)
    
    # Also read file content for storage (fallback)
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except:
        content = f"[File content could not be read as text: {filename}]"
    
    # Determine the best matching index if not provided
    if not index_key:
        index_key = match_note_to_index(content, subject, class_name)
    
    # Save note data with index structure
    notes_data = load_data(NOTES_DATA_FILE, {})
    if subject not in notes_data:
        notes_data[subject] = {}
    if class_name not in notes_data[subject]:
        notes_data[subject][class_name] = {}
    if index_key not in notes_data[subject][class_name]:
        notes_data[subject][class_name][index_key] = []
    
    # Generate unique ID across all notes
    max_id = 0
    for subj_data in notes_data.values():
        for class_data in subj_data.values():
            for idx_data in class_data.values():
                for note in idx_data:
                    if note.get('id', 0) > max_id:
                        max_id = note.get('id', 0)
    
    note_data = {
        'id': max_id + 1,
        'filename': filename,
        'original_name': file.filename,
        'content': content,
        'upload_date': datetime.now().isoformat(),
        'ai_analysis': ai_analysis,
        'index_key': index_key,
        'highlights': [],
        'questions': [],
        'stars': 0
    }
    
    notes_data[subject][class_name][index_key].append(note_data)
    save_data(NOTES_DATA_FILE, notes_data)
    
    # Update subjects data
    subjects = load_data(SUBJECTS_DATA_FILE, {})
    if subject not in subjects:
        subjects[subject] = {'classes': {}}
    if class_name not in subjects[subject]['classes']:
        subjects[subject]['classes'][class_name] = {
            'name': class_name,
            'note_count': 0,
            'created_date': datetime.now().isoformat()
        }
    
    # Ensure note_count exists and increment it
    if 'note_count' not in subjects[subject]['classes'][class_name]:
        subjects[subject]['classes'][class_name]['note_count'] = 0
    subjects[subject]['classes'][class_name]['note_count'] += 1
    save_data(SUBJECTS_DATA_FILE, subjects)
    
    return jsonify({'success': True, 'note_id': note_data['id']})

def match_note_to_index(content, subject, class_name):
    """Match note content to the best fitting textbook index"""
    indices = load_data(INDICES_DATA_FILE, {})
    
    if subject not in indices or class_name not in indices[subject]:
        return "general"
    
    index_structure = indices[subject][class_name].get('structure', [])
    if not index_structure:
        return "general"
    
    # Simple keyword matching for now
    content_lower = content.lower()
    best_match = "general"
    best_score = 0
    
    for item in index_structure:
        title_lower = item.get('title', '').lower()
        # Count how many words from the index title appear in the content
        words = title_lower.split()
        score = sum(1 for word in words if word in content_lower)
        
        if score > best_score and score > 0:
            best_score = score
            best_match = item.get('number', item.get('title', 'general').lower().replace(' ', '_'))
    
    return best_match

def analyze_file_with_ai(filepath, filename, subject, class_name, index_key=None):
    """Use Gemini AI to analyze uploaded file directly"""
    print(f"Starting AI file analysis for {subject} - {class_name}")
    print(f"File: {filename}")
    
    # Check if model is available
    if model is None:
        print("❌ AI model not available - returning basic analysis")
        return {
            "subject_match": True,
            "key_topics": ["AI analysis unavailable"],
            "important_equations": [],
            "highlights": [],
            "important_points": [],
            "test_questions": [],
            "related_links": [],
            "error": "AI model not configured - please check API key",
            "index_relevance": "Analysis not available"
        }
    
    index_context = ""
    if index_key and index_key != "general":
        index_context = f" This note appears to be related to textbook section: {index_key}."
    
    prompt = f"""
    Analyze this uploaded file for a {subject} class ({class_name}) and provide:{index_context}
    1. Subject classification (confirm if it matches {subject})
    2. Key topics/concepts covered
    3. Important equations or formulas (if any)
    4. FIVE most important points or facts with specific explanations
    5. Potential test questions
    6. Related concepts or links to explore
    7. Textbook index/chapter relevance
    
    For the important points, provide the exact text from the document and a detailed explanation.
    
    Respond in JSON format with the following structure:
    {{
        "subject_match": true/false,
        "key_topics": ["topic1", "topic2"],
        "important_equations": ["equation1", "equation2"],
        "highlights": ["text to highlight", "another highlight"],
        "important_points": [
            {{
                "text": "exact text from document",
                "explanation": "detailed explanation of why this is important",
                "type": "concept/formula/definition/example"
            }}
        ],
        "test_questions": ["question1", "question2"],
        "related_links": ["concept1", "concept2"],
        "index_relevance": "description of how this relates to textbook structure"
    }}
    """
    
    try:
        print("Uploading file to Gemini AI...")
        print(f"Using model: {model.model_name}")
        
        # Upload file to Gemini
        uploaded_file = genai.upload_file(filepath)
        print(f"✅ File uploaded successfully: {uploaded_file.name}")
        
        # Generate content using the uploaded file
        response = model.generate_content([uploaded_file, prompt])
        print(f"API Response received: {len(response.text)} characters")
        
        # Parse the JSON response from Gemini
        response_text = response.text.strip()
        print(f"Response preview: {response_text[:200]}...")
        
        # Try to extract JSON from the response
        import re
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        
        if json_match:
            json_str = json_match.group()
            ai_analysis = json.loads(json_str)
        else:
            # If no JSON found, create a basic structure from the response
            ai_analysis = {
                "subject_match": True,
                "key_topics": ["Analysis completed"],
                "important_equations": [],
                "highlights": [],
                "test_questions": [],
                "related_links": [],
                "raw_response": response_text[:500],  # Store first 500 chars of raw response
                "index_relevance": "AI analysis completed"
            }
        
        # Clean up uploaded file
        try:
            genai.delete_file(uploaded_file.name)
            print("✅ Cleaned up uploaded file")
        except:
            print("⚠️ Could not delete uploaded file (may auto-expire)")
        
        return ai_analysis
        
    except json.JSONDecodeError as e:
        # If JSON parsing fails, return the raw response
        return {
            "subject_match": True,
            "key_topics": ["AI Analysis"],
            "important_equations": [],
            "highlights": [],
            "important_points": [],
            "test_questions": [],
            "related_links": [],
            "raw_response": response.text[:500] if 'response' in locals() else "No response received",
            "json_error": str(e),
            "index_relevance": "AI analysis completed with parsing issues"
        }
    except Exception as e:
        error_msg = str(e)
        print(f"❌ AI File Analysis Error: {error_msg}")
        
        # Check for specific error types
        if "credentials" in error_msg.lower():
            error_msg = "API credentials issue - please check your API key"
        elif "model" in error_msg.lower() and "not found" in error_msg.lower():
            error_msg = "Model not found - API model name issue"
        elif "quota" in error_msg.lower():
            error_msg = "API quota exceeded - please try again later"
        elif "file" in error_msg.lower():
            error_msg = "File upload issue - please check file format and size"
        
        return {
            "subject_match": True,
            "key_topics": ["Analysis failed"],
            "important_equations": [],
            "highlights": [],
            "important_points": [],
            "test_questions": [],
            "related_links": [],
            "error": error_msg,
            "raw_error": str(e),
            "index_relevance": "AI file analysis failed"
        }

def analyze_note_with_ai(content, subject, class_name, index_key=None):
    """Use Gemini AI to analyze the note content"""
    print(f"Starting AI analysis for {subject} - {class_name}")
    print(f"Content length: {len(content)} characters")
    
    # Check if model is available
    if model is None:
        print("❌ AI model not available - returning basic analysis")
        return {
            "subject_match": True,
            "key_topics": ["AI analysis unavailable"],
            "important_equations": [],
            "highlights": [],
            "important_points": [],
            "test_questions": [],
            "related_links": [],
            "error": "AI model not configured - please check API key",
            "index_relevance": "Analysis not available"
        }
    
    index_context = ""
    if index_key and index_key != "general":
        index_context = f" This note appears to be related to textbook section: {index_key}."
    
    prompt = f"""
    Analyze this note for a {subject} class ({class_name}) and provide:{index_context}
    1. Subject classification (confirm if it matches {subject})
    2. Key topics/concepts covered
    3. Important equations or formulas (if any)
    4. FIVE most important points or facts with specific explanations
    5. Potential test questions
    6. Related concepts or links to explore
    7. Textbook index/chapter relevance
    
    For the important points, provide the exact text from the note and a detailed explanation.
    
    Note content:
    {content[:2000]}  # Limit content to avoid token limits
    
    Respond in JSON format with the following structure:
    {{
        "subject_match": true/false,
        "key_topics": ["topic1", "topic2"],
        "important_equations": ["equation1", "equation2"],
        "highlights": ["text to highlight", "another highlight"],
        "important_points": [
            {{
                "text": "exact text from document",
                "explanation": "detailed explanation of why this is important",
                "type": "concept/formula/definition/example"
            }}
        ],
        "test_questions": ["question1", "question2"],
        "related_links": ["concept1", "concept2"],
        "index_relevance": "description of how this relates to textbook structure"
    }}
    """
    
    try:
        print("Calling Gemini API...")
        print(f"Using model: {model.model_name}")
        
        response = model.generate_content(prompt)
        print(f"API Response received: {len(response.text)} characters")
        
        # Parse the JSON response from Gemini
        response_text = response.text.strip()
        print(f"Response preview: {response_text[:200]}...")
        
        # Try to extract JSON from the response
        import re
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        
        if json_match:
            json_str = json_match.group()
            ai_analysis = json.loads(json_str)
        else:
            # If no JSON found, create a basic structure from the response
            ai_analysis = {
                "subject_match": True,
                "key_topics": ["Analysis completed"],
                "important_equations": [],
                "highlights": [],
                "test_questions": [],
                "related_links": [],
                "raw_response": response_text[:500],  # Store first 500 chars of raw response
                "index_relevance": "AI analysis completed"
            }
        
        return ai_analysis
        
    except json.JSONDecodeError as e:
        # If JSON parsing fails, return the raw response
        return {
            "subject_match": True,
            "key_topics": ["AI Analysis"],
            "important_equations": [],
            "highlights": [],
            "important_points": [],
            "test_questions": [],
            "related_links": [],
            "raw_response": response.text[:500] if 'response' in locals() else "No response received",
            "json_error": str(e),
            "index_relevance": "AI analysis completed with parsing issues"
        }
    except Exception as e:
        error_msg = str(e)
        print(f"❌ AI Analysis Error: {error_msg}")
        
        # Check for specific error types
        if "credentials" in error_msg.lower():
            error_msg = "API credentials issue - please check your API key"
        elif "model" in error_msg.lower() and "not found" in error_msg.lower():
            error_msg = "Model not found - API model name issue"
        elif "quota" in error_msg.lower():
            error_msg = "API quota exceeded - please try again later"
        
        return {
            "subject_match": True,
            "key_topics": ["Analysis failed"],
            "important_equations": [],
            "highlights": [],
            "important_points": [],
            "test_questions": [],
            "related_links": [],
            "error": error_msg,
            "raw_error": str(e),
            "index_relevance": "AI analysis failed"
        }

def create_summary_note(notes):
    """Create a summary note from all notes in a class"""
    if not notes:
        return None
    
    # Extract highlights, questions, and starred content
    highlights = []
    questions = []
    starred_content = []
    
    for note in notes:
        highlights.extend(note.get('ai_analysis', {}).get('highlights', []))
        questions.extend(note.get('ai_analysis', {}).get('test_questions', []))
        if note.get('stars', 0) > 0:
            starred_content.append(note.get('content', '')[:200])
    
    summary = {
        'type': 'summary',
        'highlights': highlights[:10],  # Limit to top 10
        'questions': questions[:10],
        'starred_content': starred_content[:5],
        'total_notes': len(notes),
        'last_updated': datetime.now().isoformat()
    }
    
    return summary

@app.route('/api/note/<int:note_id>')
def get_note(note_id):
    """Get specific note data"""
    notes_data = load_data(NOTES_DATA_FILE, {})
    
    for subject_name, subject_data in notes_data.items():
        for class_name, class_data in subject_data.items():
            for index_key, index_notes in class_data.items():
                for note in index_notes:
                    if note.get('id') == note_id:
                        # Clean AI analysis before returning
                        if 'ai_analysis' in note:
                            note['ai_analysis'] = clean_ai_analysis(note['ai_analysis'])
                        return jsonify(note)
    
    return jsonify({'error': 'Note not found'}), 404

@app.route('/api/subjects')
def get_subjects():
    """Get all subjects and classes for dropdown"""
    subjects = load_data(SUBJECTS_DATA_FILE, {})
    return jsonify(subjects)

@app.route('/final-note/<subject_name>/<class_name>')
def final_note_page(subject_name, class_name):
    """Display detailed final note study guide"""
    notes_data = load_data(NOTES_DATA_FILE, {})
    indices = load_data(INDICES_DATA_FILE, {})
    class_notes = notes_data.get(subject_name, {}).get(class_name, {})
    class_indices = indices.get(subject_name, {}).get(class_name, {})
    
    # Clean AI analysis in class notes
    if class_notes:
        for index_key, index_notes in class_notes.items():
            for note in index_notes:
                if 'ai_analysis' in note:
                    note['ai_analysis'] = clean_ai_analysis(note['ai_analysis'])
    
    return render_template('final_note.html', 
                         subject_name=subject_name, 
                         class_name=class_name, 
                         class_notes=class_notes,
                         indices=class_indices)

@app.route('/api/file/<filename>')
def serve_file(filename):
    """Serve uploaded files"""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/api/note-counts')
def get_all_note_counts():
    """Get note counts for all subjects"""
    notes_data = load_data(NOTES_DATA_FILE, {})
    subject_counts = {}
    
    for subject_name, subject_data in notes_data.items():
        total_notes = 0
        for class_name, class_data in subject_data.items():
            for index_key, index_notes in class_data.items():
                total_notes += len(index_notes)
        subject_counts[subject_name] = total_notes
    
    return jsonify(subject_counts)

@app.route('/api/note-counts/<subject_name>')
def get_subject_note_counts(subject_name):
    """Get note counts for all classes in a subject"""
    notes_data = load_data(NOTES_DATA_FILE, {})
    subject_notes = notes_data.get(subject_name, {})
    
    class_counts = {}
    for class_name, class_data in subject_notes.items():
        total_notes = 0
        for index_key, index_notes in class_data.items():
            total_notes += len(index_notes)
        class_counts[class_name] = total_notes
    
    return jsonify(class_counts)

@app.route('/api/note-counts/<subject_name>/<class_name>')
def get_note_counts(subject_name, class_name):
    """Get live note counts for a class"""
    notes_data = load_data(NOTES_DATA_FILE, {})
    class_notes = notes_data.get(subject_name, {}).get(class_name, {})
    
    note_counts = {}
    for index_key, index_notes in class_notes.items():
        note_counts[index_key] = len(index_notes)
    
    return jsonify(note_counts)

@app.route('/api/indices/<subject_name>/<class_name>')
def get_indices(subject_name, class_name):
    """Get indices for a specific class"""
    indices = load_data(INDICES_DATA_FILE, {})
    
    if subject_name in indices and class_name in indices[subject_name]:
        index_data = indices[subject_name][class_name]
        return jsonify({
            'structure': index_data.get('structure', []),
            'has_index': True
        })
    else:
        return jsonify({
            'structure': [],
            'has_index': False
        })

if __name__ == '__main__':
    app.run(debug=True)
