from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from pymongo import MongoClient
from bson import ObjectId
import re
import bcrypt


 
app = Flask(__name__)
app.secret_key = 'xyzsdfg'

# Initialize MongoDB client
client = MongoClient("mongodb+srv://admin:password101@quizbank.tx6gspj.mongodb.net/")
db = client.get_database("translations")
users_collection = db.users
cards_collection = db.bank
quiz_collection = db.quiz

def is_user_logged_in():
    return 'user_id' in session

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

#Check if user session is true
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
                    # Add other user details
                }
            }
            return jsonify(user_info), 200
    return jsonify({"logged_in": False}), 200

#User Login
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


# User Logout 
@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('index'))

#creating restful friendly endpoints to interact with postman/react
# User registration
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
                'password': hashed_password  # Store the hashed password as bytes
            }
            users_collection.insert_one(user_data)
            message = 'You have successfully registered!'
            
            return redirect(url_for('login', registration_success=True))

    return render_template('register.html', message=message, first_name=first_name)

#Quiz Endpoint
#Create Quiz
# @app.route('/quiz/get-quiz')
# def get_quiz():

# #create quiz
# @app.route('/quiz/create-quiz')
# def create_quiz():



#Questions Endpoint
#Create Question
@app.route('/create_card', methods=['GET','POST'])
def create_card():
    first_name = None
    user_logged_in = is_user_logged_in()
    if user_logged_in:
        # Fetch the first_name based on user_id
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

        # Create the book data
        card_data = {
            "english":english,
            "translation": translation,
            "difficulty": difficulty,
            "category": category
        }
        english = cards_collection.insert_one(card_data).inserted_id

        # Connect the author to the book in bookauthor_collection
        cards_collection.insert_one({"english": english})
        message = 'Card created successfully!'

        english = cards_collection.find()
        return render_template("add_card.html", message=message, english=english, user_logged_in=user_logged_in, first_name=first_name)

    english = cards_collection.find()
    return render_template("add_card.html", english=english, user_logged_in=user_logged_in, first_name=first_name)



#Delete Question
@app.route('/card/delete', methods=['POST'])
def delete_card():
    if not is_user_logged_in():
        return jsonify({"message": "You must be logged in to delete a Card."}), 401
    user = users_collection.find_one({'_id': ObjectId(session['user_id'])})

    if not user:
        return jsonify({"message": "You must be logged in to delete a Card."}), 401
    data = request.get_json()
    
    if not data:
        return jsonify({"message": "Request data missing."}), 400
    english = data.get('english')
    if not english:
        return jsonify({"message": "Please provide the English translation of the card to delete."}), 400


    deleted_card = cards_collection.find_one_and_delete({'english': english})
    if not deleted_card:
        return jsonify({"message": "Card not found."}), 404

    return jsonify({"message": "Card deleted successfully."}), 200

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
    
    # Build the MongoDB query based on search_term and category (if provided)
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


if __name__ == "__main__":
    app.run(host='localhost', port=5001, debug=True)