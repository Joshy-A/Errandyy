from flask import Blueprint, render_template, request, url_for, redirect, session, flash, jsonify, current_app
from myapp.database import *
# from functools import wraps
from flask_login import login_user, logout_user, current_user, login_required
from datetime import datetime

import pandas as pd
import matplotlib.pyplot as plt
from myapp import socket

views = Blueprint('views', __name__, static_folder='static', template_folder='templates')

# Register a new user and hash password
@views.route("/register", methods=["GET", "POST"])
def register():
    """
    Handles user registration and password hashing.

    Returns:
        Response: Flask response object.
    """
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        username = request.form["username"].strip().lower()
        password = request.form["password"]

        # Check if the user already exists
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash("User already exists with that username.")
            return redirect(url_for("views.login"))

        # Create a new user
        new_user = User(username=username, email=email, password=password)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()

        # Create a new chat list for the newly registered user
        new_chat = Chat(user_id=new_user.id, chat_list=[])
        db.session.add(new_chat)
        db.session.commit()

        flash("Registration successful.")
        return redirect(url_for("views.login"))

    return render_template("auth.html")

# Login a Registered user with email and hash password
@views.route("/login", methods=["GET", "POST"])
def login():
    """
    Handles user login and session creation.

    Returns:
        Response: Flask response object.
    """
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]

        # Query the database for the inputted email address
        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            # Create a new session for the newly logged-in user
            session["user"] = {
                "id": user.id,
                "username": user.username,
                "email": user.email,
            }
            login_user(user, remember=True)
            return redirect(url_for("views.home"))
        else:
            flash("Invalid login credentials. Please try again.")
            return redirect(url_for("views.login"))

    return render_template("auth.html", user = current_user)

# Render home html templates
@views.route('/', methods=['GET', 'POST'])
@login_required
def home():
    requests = Request.query.all()
    return render_template('home.html', requests=requests, user=current_user)

# Render home html but allows users to create errands
@views.route("/create", methods=['POST'])
@login_required
def create():   
    """
    Creates a new request.

    Returns:
        Response: Flask response object.
    """
    title = request.form.get('title')
    description = request.form.get('description')
    
    if not title or not description:
        flash('Title and description are required fields.', category='error')
        return redirect(url_for('views.home'))

    # Create a new request associated with the current user
    new_request = Request(title=title, description=description, user_id=current_user.id)
    db.session.add(new_request)
    db.session.commit()
    
    flash('Request created successfully!', category='success')
    return redirect(url_for('views.home'))

# This routes is used to render the chat room between the requester and the responder
@views.route('/message/<int:request_id>', methods=['POST'])
@login_required
def send_message(request_id):
    # Retrieve the request associated with the given request_id
    request_obj = Request.query.get_or_404(request_id)

    # Check if the current user is authenticated and has a valid email
    if not current_user.is_authenticated or not current_user.email:
        flash('You need to be authenticated with a valid email to send a message.', category='error')
        return redirect(url_for('views.home'))

    # Retrieve the email of the recipient from the request
    new_chat_email = request.form.get("requester_email")

    # If user is trying to add themselves, do nothing
    if new_chat_email == current_user.email:
        return redirect(url_for("views.chat"))

    # Check if the recipient user exists
    recipient_user = User.query.filter_by(email=new_chat_email).first()
    if not recipient_user:
        flash('Recipient user does not exist.', category='error')
        return redirect(url_for("views.chat"))

    # Call the new_chat function to create a new chat room
    room_id = new_chat(new_chat_email)  # Pass the email to the new_chat function

    # Now, proceed with sending the message
    # Assuming you have a message content obtained from the request
    message_content = "Hello, I can help you."
    timestamp = datetime.now()
    
    # Create a new chat message object
    new_message = ChatMessage(
        content=message_content,
        timestamp=timestamp,  # Corrected spelling of timestamp
        sender_id=current_user.id,
        sender_username=current_user.username,
        room_id=room_id
    )
    
    # Save the message to the database
    db.session.add(new_message)
    db.session.commit()

    return redirect(url_for("views.chat"))


# This route allows users to create a new chat room adding the email of a registered users
@views.route("/new-chat", methods=["POST"])
@login_required
def new_chat(new_chat_email):  # Accept the email as a parameter
    """
    Creates a new chat room and adds users to the chat list.

    Parameters:
        new_chat_email (str): The email of the recipient user.

    Returns:
        str: The room ID of the newly created chat room.
    """
    user_id = session["user"]["id"]

    # If user is trying to add themselves, do nothing
    if new_chat_email == session["user"]["email"]:
        return redirect(url_for("views.chat"))

    # Check if the recipient user exists
    recipient_user = User.query.filter_by(email=new_chat_email).first()
    if not recipient_user:
        return redirect(url_for("views.chat"))

    # Check if the chat already exists
    existing_chat = Chat.query.filter_by(user_id=user_id).first()
    """if not existing_chat:
        existing_chat = Chat(user_id=user_id, chat_list=[])
        db.session.add(existing_chat)
        db.session.commit()"""

    # Check if the new chat is already in the chat list
    if recipient_user.id not in [user_chat["user_id"] for user_chat in existing_chat.chat_list]:
        # Generate a room_id (you may use your logic to generate it)
        room_id = str(int(recipient_user.id) + int(user_id))[-4:]

        # Add the new chat to the chat list of the current user
        updated_chat_list = existing_chat.chat_list + [{"user_id": recipient_user.id, "room_id": room_id}]
        existing_chat.chat_list = updated_chat_list

        # Save the changes to the database
        existing_chat.save_to_db()

        # Create a new chat list for the recipient user if it doesn't exist
        recipient_chat = Chat.query.filter_by(user_id=recipient_user.id).first()
        if not recipient_chat:
            recipient_chat = Chat(user_id=recipient_user.id, chat_list=[])
            db.session.add(recipient_chat)
            db.session.commit()

        # Add the new chat to the chat list of the recipient user
        updated_chat_list = recipient_chat.chat_list + [{"user_id": user_id, "room_id": room_id}]
        recipient_chat.chat_list = updated_chat_list
        recipient_chat.save_to_db()

        # Create a new message entry for the chat room
        new_message = Message(room_id=room_id)
        db.session.add(new_message)
        db.session.commit()

        return room_id  # Return the room ID

    return redirect(url_for("views.chat"))


@views.route("/chat/", methods=["GET", "POST"])
@login_required
def chat():
    """
    Renders the chat interface and displays chat messages.

    Returns:
        Response: Flask response object.
    """
    # Get the room id in the URL or set to None
    room_id = request.args.get("rid", None)

    # Get the chat list for the user
    current_user_id = session["user"]["id"]
    current_user_chats = Chat.query.filter_by(user_id=current_user_id).first()
    chat_list = current_user_chats.chat_list if current_user_chats else []

    # Initialize context that contains information about the chat room
    data = []

    for chat in chat_list:
        # Query the database to get the username of users in a user's chat list
        username = User.query.get(chat["user_id"]).username
        is_active = room_id == chat["room_id"]

        try:
            # Get the Message object for the chat room
            message = Message.query.filter_by(room_id=chat["room_id"]).first()

            # Get the last ChatMessage object in the Message's messages relationship
            last_message = message.messages[-1]

            # Get the message content of the last ChatMessage object
            last_message_content = last_message.content
        except (AttributeError, IndexError):
            # Set variable to this when no messages have been sent to the room
            last_message_content = "This place is empty. No messages ..."

        data.append({
            "username": username,
            "room_id": chat["room_id"],
            "is_active": is_active,
            "last_message": last_message_content,
        })

    # Get all the message history in a certain room
    message_entry = Message.query.filter_by(room_id=room_id).first()
    messages = message_entry.messages if message_entry else []

    if request.method == 'POST':
        # Get the content of the new message from the form
        chat_message_content = request.form.get('message')

        # Ensure the message content is not empty
        if chat_message_content:
            # Create a new ChatMessage object for the new message
            new_message = ChatMessage(
                content=chat_message_content,
                sender_id=current_user_id,
                room_id=room_id
            )
            # Add the new message to the database
            db.session.add(new_message)
            db.session.commit()

            # Redirect back to the chat page to refresh the messages
            return redirect(url_for('views.chat', rid=room_id))

    return render_template(
        "chat.html",
        user_data=session["user"],
        room_id=room_id,
        data=data,
        messages=messages,
        user=current_user
    )

# Custom time filter to be used in the jinja template
@views.app_template_filter('ftime')
def ftime(date):
    try:
        # Convert the integer timestamp to string
        date_str = str(date)
        # Parse the timestamp string to a datetime object
        dt = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S.%f')  # Adjust format as needed
    except ValueError:
        # Handle if the timestamp string cannot be parsed
        return 'Invalid timestamp format'
    
    # Format the datetime object as needed
    formatted_date = dt.strftime('%Y-%m-%d %H:%M:%S')
    return formatted_date


# This routes allows users to view more information about an errand
@views.route('/view-request/<int:request_id>', methods=['GET'])
@login_required
def view_request(request_id):
    # Fetch the request data from the database
    request_data = Request.query.get_or_404(request_id)
    
    # Pass the request data to the viewrequest.html template
    return render_template('view_request.html', request=request_data, user=current_user)

@views.route('/delete-account', methods=['POST'])
@login_required
def delete_account():
    user = User.query.get(current_user.id)

    if user:
        logout_user()
        db.session.delete(user)
        db.session.commit()

        flash('Your account has been deleted successfully!', category='success')
        return redirect(url_for('auth.login'))
    else:
        flash('User not found', category='error')
        return redirect(url_for('views.home'))
    
@views.route('/delete/<int:id>', methods=['POST'])
def delete(id):
    requests = Request.query.get_or_404(id)
    
    if requests.user != current_user:
        flash('You cannot delete this request.', category='error')

    else:
        
        db.session.delete(requests)
        db.session.commit()
        
        flash('Requests Deleted!', category='success')
    return redirect(url_for('views.home'))


@views.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully!', category='success')
    return redirect(url_for('views.login'))

@views.route('/visualize')
def visualize():
    """
    TODO: Utilize pandas and matplotlib to analyze the number of users registered to the app.
    Create a chart of the analysis and convert it to base64 encoding for display in the template.

    Returns:
        Response: Flask response object.
    """
    pass


@views.route('/get_name')
def get_name():
    """
    :return: json object with username
    """
    data = {'name': ''}
    if 'username' in session:
        data = {'name': session['username']}

    return jsonify(data)


@views.route('/get_messages')
def get_messages():
    """
    query the database for messages o in a particular room id
    :return: all messages
    """
    pass


@views.route('/leave')
def leave():
    """
    Emits a 'disconnect' event and redirects to the home page.

    Returns:
        Response: Flask response object.
    """
    socket.emit('disconnect')
    return redirect(url_for('views.home'))
