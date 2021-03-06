from os.path import join, dirname
import os
from dotenv import load_dotenv
from datetime import datetime
import flask
import flask_socketio
import flask_sqlalchemy
from sqlalchemy import asc, desc
import random
import timeago
import json
from flask_socketio import join_room, leave_room

app = flask.Flask(__name__)
socketio = flask_socketio.SocketIO(app)
socketio.init_app(app, cors_allowed_origins="*")

DOTENV_PATH = join(dirname(__file__), "sql.env")
load_dotenv(DOTENV_PATH)

DATABASE_URI = os.environ["DATABASE_URL"]
app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URI

DB = flask_sqlalchemy.SQLAlchemy(app)

import models
from spotify_login import get_user, get_artists, get_top_artists, get_current_song, get_num_listeners, get_top_tracks
from spotify_music import spotify_get_trending, spotify_get_recommended
from spotify_music import spotify_search_track, spotify_search_artist, spotify_search_album, spotify_search_playlist
from ticketmaster_api import search_events

DB.init_app(app)
DB.app = app

app.static_folder = 'static'

def get_username(flask_id):
    user = models.ActiveUsers.query.filter_by(serverid = flask_id).first().user
    DB.session.commit()
    return user

def query_user(user):
    user = models.Users.query.filter_by(username = user).first()
    DB.session.commit()
    return user

def get_post_music_data(music_type, music_data):
    data = {}
    
    song = music_data['song'].strip()
    artist = music_data['artist'].strip()
    album = music_data['album'].strip()
    playlist = music_data['playlist'].strip()

    if music_type == "song":
        data = spotify_search_track(song, artist)
    if music_type == "artist":
        data = spotify_search_artist(artist)
    elif music_type == "album":
        data = spotify_search_album(album, artist)
    elif music_type == "playlist":
        data = spotify_search_playlist(playlist)
    
    return data

@socketio.on('user post channel')
def on_post_receive(data):

    username = data['user']['username']
    pfp = data['user']['pfp']
    
    music_type = data['type']
    music_entry = get_post_music_data(music_type, data['music'])
    
    message = data['text']
    num_likes = 0
    time = datetime.now()
    
    post = models.Posts(username, pfp, music_type, music_entry, message, num_likes, time)

    DB.session.add( post )
    DB.session.commit()

    
    post_dict = {
        "id": post.id,
        "username": post.username,
        "text": post.message,
        "num_likes": post.num_likes,
        "datetime": post.datetime.strftime("%m/%d/%Y, %H:%M:%S"),
        "pfp": post.pfp,
        "comments": [],
        "is_liked": False,
        "isCommentsOpen": False,
        "music_type" : post.music_type,
        "music" : post.music
    }
        
    socketio.emit('emit new post channel', post_dict)

def emit_posts():
    
    if models.Posts.query.count() == 0:
        DB.session.commit()
        return None
    DB.session.commit()
    posts = []
    all_posts = DB.session.query(models.Posts).order_by(desc(models.Posts.datetime)).all()
    DB.session.commit()
    for post in all_posts:
        entry = {
                "id": post.id,
                "username": post.username,
                "text": post.message,
                "num_likes": post.num_likes,
                "datetime": post.datetime.strftime("%m/%d/%Y, %H:%M:%S"),
                "pfp": post.pfp,
                "isCommentsOpen": False,
                "comments": [
                                { 
                                    "text": comment.text,
                                    "username": comment.username,
                                    "datetime": timeago.format(comment.datetime, datetime.now())
                                }
                            for comment in DB.session.query(models.Comments).filter(models.Comments.post_id == post.id).order_by(desc(models.Comments.datetime)).all()
                            ],
                "is_liked": DB.session.query(models.Likes).filter(models.Likes.username == post.username,models.Likes.post_id == post.id).scalar() is not None,
                "music_type" : post.music_type,
                "music" : post.music
        }
        
        posts.append( entry )
   
    socketio.emit('emit posts channel', posts)


def add_or_remove_like_from_db(user, liked_post_id):
    is_liked = DB.session.query(models.Likes.id).filter_by(username=user, post_id=liked_post_id).scalar() is not None
    DB.session.commit()
    if (is_liked):
        DB.session.query(models.Likes).filter_by(username=user, post_id=liked_post_id).delete()
    else:
        DB.session.add(models.Likes(user, liked_post_id))
    DB.session.commit()
    return not is_liked
    
@socketio.on('like post')    
def update_num_likes(data):
    num_likes = data["num_likes"]
    post_id = data["id"]

    post_to_like = DB.session.query(models.Posts).filter(models.Posts.id == post_id).update({models.Posts.num_likes: num_likes}, synchronize_session = False) 
    DB.session.commit()
    
    username = get_username(flask.request.sid)
    is_liked = add_or_remove_like_from_db(username, post_id)
    
    socketio.emit("like post channel", {"post_id": post_id, "num_likes":num_likes,  "is_liked": is_liked})

    
def emit_user_data(userInfo, topArtists, currSong):

    
    artistList = []
    if len(topArtists) != 0:
        artistList.append(topArtists[0])
        artistList.append(topArtists[1])
        artistList.append(topArtists[2])
        
    socketio.emit('emit user data', {'username':userInfo['username'],'profileType':userInfo['user_type'], 'topArtists':artistList, 'following':['Cat', 'Dhvani','Justin'], 'currentSong':currSong})
    


def emit_artist_data(userInfo, topTracks, numListeners):

    socketio.emit('emit user data', {'username':userInfo['username'],'profileType':userInfo['user_type'], 'topTracks':topTracks, 'numListeners':numListeners, 'following':['Cat', 'Dhvani','Justin']})

def emit_recommended():
    
    username = get_username(flask.request.sid)
    query_users = query_user(username)

    recommended = get_recommended( query_users.top_artists )
    
    if recommended == None:
        return
    
    socketio.emit('recommended channel', recommended, room=flask.request.sid)

def get_recommended( user_top_artists ):
    
    if len(user_top_artists) == 0:
        return None
    
    # keep only spotify ID
    for i in range(len(user_top_artists)):
        user_top_artists[i] = user_top_artists[i].split(":")[2]

    sample_artists = random.sample( user_top_artists, 3 )

    recommended = spotify_get_recommended(sample_artists)
    return recommended


def emit_trending():
    
    trending = get_trending()
    socketio.emit('trending channel', trending, room=flask.request.sid)
    
def get_trending():
    
    # if DB empty, get trending
    # TODO later add timestamp and check daily
    if (models.Trending.query.count() == 0):
        data = spotify_get_trending()
        for item in data:
            track = item['track']['name']
            artist = []
            for item_artist in item['track']['artists']:
                artist.append(item_artist['name'])
        
            DB.session.add(models.Trending(track, artist))
            DB.session.commit()
        
        DB.session.commit()
    
    trending_query = models.Trending.query.all()
    DB.session.commit()
    sample = random.sample(trending_query, 3)
    
    trending = []
    for song in sample:
        track = {}

        track['artist'] = ", ".join(song.artists)
        track['song'] = song.track
        
        trending.append( track )
    
    return trending

@socketio.on("get local storage")
def get_local_storage():
    socketio.emit('navigation change', True)

@socketio.on('new spotify user')
def on_spotlogin(data):
    """
    Runs the code in spotify_login and adds it to the db
    """
    user=get_user(data['token'])
    artists=get_artists(data['token'])
    
    # add to users if not already, update top artists
    usersquery = query_user(user['username'])
    if (usersquery == [] or usersquery == None):
        db_user=models.Users(
                        username=user['username'],
                        profile_picture=user['profile-picture'],
                        user_type=user['user-type'],
                        top_artists=artists,
                        following=[],
                        my_likes=[]
                        )
        DB.session.add(db_user)
        DB.session.commit()
    else:
        usersquery.top_artists = artists

    # emit success to user, so they can access timeline
    socketio.emit('login success', {'status':True,'userinfo':{'username':user['username'],'pfp':user['profile-picture']}}, room=flask.request.sid)

    
    # add to active users table
    DB.session.add(models.ActiveUsers(user['username'], flask.request.sid, data['token']))
    
    # commit all db changes
    DB.session.commit()
    
 # tell view to get local storage on navigation change
@socketio.on('get local storage')
def emit_local_storage(data):
    if(data):
        # emit success to user, so they can access timeline
        socketio.emit('get posts from local storage', True) 
        
 # tell view to get local storage on navigation change
@socketio.on('get user local storage')
def emit_user_local_storage(data):
    if(data):
        # emit success to user, so they can access timeline
        socketio.emit('get user from local storage', True) 

# emit trending and recommended and posts
@socketio.on('user logged in')
def user_logged_in(data):
    if data:
        emit_posts()
        emit_recommended()
        emit_trending()
        send_user_profile(get_username(flask.request.sid))

    
@socketio.on("get profile")
def send_user_profile(data):
    print("HERE")
    username = data
    topArtists=get_top_artists(username)
    currSong=get_current_song(username)

    usertype = query_user(username)
    userinfo = {'username': username, 'user_type': usertype.user_type}
    

    if usertype is "artist":
        topTracks = get_top_tracks(flask.request.sid)
        numListeners = get_num_listeners(flask.request.sid)
        emit_artist_data(userinfo, topTracks, numListeners)
        
    else:
        emit_user_data(userinfo, topArtists, currSong)


@socketio.on('post comment')
def save_comment(data):
    username = data['username']
    time = datetime.now()
    comment = models.Comments(username, data['comment'], data['post_id'], time)
    DB.session.add(comment)
    DB.session.commit()
    
    comment = { 
        "text": data['comment'],
        "username": username,
        "datetime": timeago.format(time, datetime.now())
    }
    socketio.emit("NEW COMMENT ON POST", {"post_id": data['post_id'], "comment": comment})

@socketio.on("search ticketmaster")
def get_ticketmaster_events(data):
    zipcode = data['zipcode']
    artist = data['artist']
    events = search_events(zipcode, artist, str(0))
    if( zipcode=="" and artist==""):
        events = []
    if(events == None ):
        events = []
    socketio.emit("display events", events)

@app.route('/')
def hello():
    return flask.render_template('index.html')

@socketio.on('connect')
def on_connect():
    join_room( flask.request.sid )
    
    print('Someone connected!')
    socketio.emit('connected', {
        'test': 'Connected'
    })

@socketio.on('disconnect')
def on_disconnect():
    print ('Someone disconnected!')

if __name__ == '__main__': 
    socketio.run(
        app,
        host=os.getenv('IP', '0.0.0.0'),
        port=int(os.getenv('PORT', 8080)),
        debug=True
    )

