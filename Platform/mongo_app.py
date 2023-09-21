from flask import json, Flask, render_template, request, redirect, url_for, session, flash, jsonify
from pymongo import MongoClient
from bson import json_util, ObjectId
from datetime import datetime
import re
import bcrypt
import random
 
app = Flask(__name__, static_url_path='/static')
app.secret_key = 'xyzsdfg'

# Initialize MongoDB client
client = MongoClient("mongodb+srv://admin:password101@quizbank.tx6gspj.mongodb.net/")
db = client.get_database("translations")
users_collection = db.users
cards_collection = db.bank
quiz_collection = db.quiz

def is_user_logged_in():
    return 'user_id' in session

def parse_json(data):
    return json.loads(json_util.dumps(data))
  
@app.route('/')
def root():
    return redirect(url_for('index'))

@app.route('/index')
def index():
    first_name = None
    last_name = None
    user_logged_in = is_user_logged_in()
    if user_logged_in:
        user = users_collection.find_one({'_id': ObjectId(session['user_id'])})
        if user:
            first_name = user.get('first_name')
            last_name = user.get('last_name')
    return render_template('index.html',user_logged_in=user_logged_in,first_name = first_name,last_name= last_name)


@app.route('/check-login', methods=['GET'])
def check_login():
    if 'user_id' in session:
        user_id = session['user_id']
        user = users_collection.find_one({'_id': ObjectId(user_id)})
        if user:
            user_info = {
                "logged_in": True,
                "user": {
                    "first_name": user.get('first_name'),
                    "last_name": user.get('last_name'),
                }
            }
            return jsonify(user_info), 200
    return jsonify({"logged_in": False}), 200


@app.route('/login', methods=['GET','POST'])
def login():
    registration_success = request.args.get('registration_success')
    
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = users_collection.find_one({'username': username})
        if user and bcrypt.checkpw(password.encode('utf-8'), user['password']):
            session['user_id'] = str(user['_id'])
            return redirect(url_for('index'))
        else:
            return render_template('login.html', message='Invalid credentials')
    return render_template('login.html', registration_success=registration_success)


@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('index'))


@app.route('/register', methods=['POST','GET'])
def register():
    message = ''
    first_name = None
    if request.method == 'POST':
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        if not all([first_name, last_name, username, email, password]):
            message = 'Please fill out all the fields!'
        elif not re.match(r'[^@]+@[^@]+\.[^@]+', email):
            message = 'Invalid email address!'
        elif users_collection.find_one({'email': email}):
            message = 'Account already exists!'
        else:
            hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
            user_data = {
                'first_name': first_name,
                'last_name': last_name,
                'username': username,
                'email': email,
                'password': hashed_password 
            }
            users_collection.insert_one(user_data)
            message = 'You have successfully registered!'
            
            return redirect(url_for('login', registration_success=True))

    return render_template('register.html', message=message, first_name=first_name)

#Quiz Endpoint
#Get Quiz
@app.route('/quizzes', methods=['GET'])
def get_all_quizzes():
    if is_user_logged_in():
        # retrieve all the quizzes
        quizzes = parse_json(quiz_collection.find({}))

    if not is_user_logged_in():
        return redirect(url_for('login'))
        
    return render_template('quiz.html', user_logged_in=is_user_logged_in(), quizzes=quizzes)

#Take the quiz
@app.route('/take_quiz', methods=['GET', 'POST'])
def take_quiz():
    if is_user_logged_in():
        # getting the quiz id from url
        quiz_id = request.args.get('quiz_id')

        quiz = parse_json(quiz_collection.find_one({'_id': ObjectId(quiz_id)}))
        if not quiz:
            return jsonify([{"message": "Quiz with the given id not found"}]), 404
        
    if not is_user_logged_in():
        return redirect(url_for('login'))

    return render_template('take_quiz.html', user_logged_in=is_user_logged_in(), quiz=quiz)

@app.route('/quiz/score', methods=['GET'])
def quiz_score():
    score = request.args.get('score', type=int)
    total_questions = request.args.get('total_questions', type=int)
    quiz_name = request.args.get('quiz_name')

    if score is None or total_questions is None or quiz_name is None:
        return jsonify({"message": "Please provide the relevant information for this page"}), 400
    
    percentage = round(100*(score / total_questions), 2)
    return render_template('quiz_result.html', user_logged_in=is_user_logged_in(), score=score, total_questions=total_questions, percentage=percentage, quiz_name=quiz_name)


#create quiz
@app.route('/quiz/create_quiz', methods=['GET','POST'])
def create_quiz():
    user_logged_in = is_user_logged_in()
    if user_logged_in:
        # Will be empty at the start
        quiz_insert_success = request.args.get('result')

        user = users_collection.find_one({'_id': ObjectId(session['user_id'])})
        if user:
            #get user name
            user_first_name = user.get('first_name')
            user_last_name = user.get('last_name')

    if not user_logged_in:
        return redirect(url_for('login'))
    
    if request.method == "POST":
        # Getting the quiz data prepared
        now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        quiz_name = request.form.get('name')
        difficulty = int(request.form.get("difficulty"))

        # Obtaining the quiz questions 
        quiz_ids = request.form.getlist("selectedCards")

        quiz_ids = [ObjectId(question) for question in quiz_ids]

        quiz_questions = []

        for id in quiz_ids:
            question_doc = cards_collection.find_one({"_id": ObjectId(id)})
            if question_doc:
                new_doc = {
                    'card_id': question_doc["_id"],
                    'english': question_doc["english"]
                }
                quiz_questions.append(new_doc)

        #Creating the quiz data
        quiz_data = {
            "user_name": user_first_name + " " + user_last_name,
            "quiz_name": quiz_name,
            "flashcards": quiz_questions,
            "difficulty": difficulty,
            "num_of_questions": len(quiz_questions),
            "timestamp": now
        }
        
        result = quiz_collection.insert_one(quiz_data)
        success = False
        if str(result.inserted_id):
            success = True

        return redirect(url_for('create_quiz', result=success))    
    # Getting the list of questions information
    cards = cards_collection.find({})
    return render_template("add_quiz.html", questions_list=cards, user_logged_in=user_logged_in, result=quiz_insert_success)

#Getting random answers and the correct answer
@app.route('/get_random_answers', methods=['GET'])
def get_random_answers():
    #retreive the answer for the question first
    card_id = request.args.get('card_id')

    if card_id:
        options = []
        card = parse_json(cards_collection.find_one({'_id': ObjectId(card_id)}))
        if card:
            # getting the correct answer option
            correct_answer = card['translation']  
            options.append(correct_answer)          
        else:
            return jsonify([{"message": "Card with the given id not found"}]), 404
        
        # now retrieving three other random options 
        query = [
            {
                "$match": {
                    "_id": {"$ne": ObjectId(card_id)} # we have to exclude the correct answer
                 }
            },
            {
                "$sample": {"size": 3}
            }
        ]
        
        result = list(cards_collection.aggregate(query))
        for card in result:
            options.append(card["translation"])
        
        random.shuffle(options)
        return jsonify( {"options": options, "correct_answer": correct_answer} ), 200
    else:
        return jsonify([{"message": "Invalid card id value"}]), 400




#Questions Endpoint
#Create Question
@app.route('/create_card', methods=['GET','POST'])
def create_card():
    first_name = None
    user_logged_in = is_user_logged_in()
    if user_logged_in:

        user = users_collection.find_one({'_id': ObjectId(session['user_id'])})
        if user:
            first_name = user.get('first_name')

    if not user_logged_in:
        return redirect(url_for('login'))

    if request.method == "POST":
        english = request.form.get("english")
        translation = request.form.get("translation")
        difficulty = int(request.form.get("difficulty"))
        category = request.form.get("category")

        card_data = {
            "english":english,
            "translation": translation,
            "difficulty": difficulty,
            "category": category
        }

        cards_collection.insert_one(card_data)
        message = 'Card created successfully!'

        english = cards_collection.find()
        return render_template("add_card.html", message=message, english=english, user_logged_in=user_logged_in, first_name=first_name)

    english = cards_collection.find()
    return render_template("add_card.html", english=english, user_logged_in=user_logged_in, first_name=first_name)


@app.route('/card/delete/<card_english>', methods=['POST'])
def delete_card(card_english):
    first_name = None
    user_logged_in = is_user_logged_in()
    if user_logged_in:
        user = users_collection.find_one({'_id': ObjectId(session['user_id'])})
        if user:
            first_name = user.get('first_name')

    if not user_logged_in:
        return redirect(url_for('login'))

    # Check if the card with the specified English text exists
    card = cards_collection.find_one({"english": card_english})
    if card:
        # Card exists, so delete it
        cards_collection.delete_one({"english": card_english})
        message = 'Card deleted successfully!'
        return redirect(url_for('get_card_list'))
    else:
        message = 'Card not found.'
        return jsonify({"message": message}), 404  # Return a JSON response indicating failure

    return redirect(url_for('get_card_list'))


@app.route('/card/list', methods=['GET'])
def get_card_list():
    user_logged_in = is_user_logged_in()
    first_name = None
    if user_logged_in:
        user = users_collection.find_one({'_id': ObjectId(session['user_id'])})
        if user:
            first_name = user.get('first_name')

    search_term = request.args.get('searchTerm')
    category = request.args.get('category')

    query = {}
    cards = cards_collection.find(query)
    
    return render_template("cards.html", cards= cards, user_logged_in=user_logged_in, first_name=first_name)


@app.route('/get-cards-by-category', methods=['GET'])
def get_cards_by_category():
    category = request.args.get('category')

    query = {}
    if category:
        query['category'] = category
    else:
        return jsonify({"message": "Invalid category value."}), 400
    cards = cards_collection.find(query)

    card_list = []
    for english in english:
        card_item = {
            'question': cards['question'],
            'answer': cards['answer'],
            'category': cards['category'],
            'difficulty': cards['difficulty']
        }

    return jsonify(card_list), 200

@app.route('/get-cards-by-difficulty', methods=['GET'])
def get_cards_by_difficulty():
    difficulty = request.args.get('difficulty', type=int)

    query = {}
    if 0 <= difficulty <= 5:
        if difficulty != 0:
            query['difficulty'] = difficulty
    else:
        return jsonify([{"message": "Invalid difficulty value."}]), 400
    
    cards = cards_collection.find(query)

    card_list = [{'_id': str(card['_id']), 'english': card['english'], 'translation': card['translation']} for card in cards]

    return jsonify(card_list), 200



if __name__ == "__main__":
    app.run(host='localhost', port=5001, debug=True)