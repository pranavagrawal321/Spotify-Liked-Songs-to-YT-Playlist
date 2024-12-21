import spotipy
from spotipy.oauth2 import SpotifyOAuth
import os
import google.oauth2.credentials
import google_auth_oauthlib.flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.auth.transport.requests import Request
from dotenv import load_dotenv
import os

load_dotenv()

CLIENT_ID = os.get_env('CLIENT_ID')
CLIENT_SECRET = os.get_env("CLIENT_SECRET")
REDIRECT_URI = 'http://localhost:8888/callback'

YOUTUBE_CLIENT_SECRET_FILE = 'client_secret.json'
SCOPES = ['https://www.googleapis.com/auth/youtube']
API_SERVICE_NAME = "youtube"
API_VERSION = "v3"

sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    redirect_uri=REDIRECT_URI,
    scope="user-library-read"
))


def get_spotify_liked_songs():
    results = sp.current_user_saved_tracks(limit=50)
    songs = []
    while results:
        for item in results['items']:
            songs.append({
                'track': item['track']['name'],
                'artist': item['track']['artists'][0]['name']
            })
        if results['next']:
            results = sp.next(results)
        else:
            break
    return songs


def get_authenticated_service():
    creds = None
    if os.path.exists("token.json"):
        creds = google.oauth2.credentials.Credentials.from_authorized_user_file("token.json", SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(
                YOUTUBE_CLIENT_SECRET_FILE, SCOPES)
            creds = flow.run_local_server(port=8080)

        with open("token.json", "w") as token:
            token.write(creds.to_json())

    try:
        service = build(API_SERVICE_NAME, API_VERSION, credentials=creds)
        return service
    except HttpError as e:
        print(f"An HTTP error {e.resp.status} occurred:\n{e.content}")
        return None


def get_existing_playlist_id(youtube, playlist_name):
    request = youtube.playlists().list(
        part='snippet',
        mine=True,
        maxResults=50
    )
    response = request.execute()



    for playlist in response.get('items', []):
        if playlist['snippet']['title'] == playlist_name:
            return playlist['id']
    return None


def get_or_create_playlist(youtube, playlist_name):
    playlist_id = get_existing_playlist_id(youtube, playlist_name)
    if playlist_id:
        print(f"Playlist '{playlist_name}' already exists. Adding songs to it...")
        return playlist_id

    print(f"Creating a new playlist named '{playlist_name}'...")
    request_body = {
        'snippet': {
            'title': playlist_name,
            'description': 'Playlist transferred from Spotify Liked Songs',
            'tags': ['Spotify', 'YouTube Music', 'Playlist'],
            'defaultLanguage': 'en'
        },
        'status': {
            'privacyStatus': 'public'
        }
    }

    response = youtube.playlists().insert(
        part='snippet,status',
        body=request_body
    ).execute()

    return response['id']


def add_songs_to_youtube_playlist(youtube, playlist_name, songs):
    playlist_id = get_or_create_playlist(youtube, playlist_name)

    for song_dict in songs:
        try:
            song = song_dict['track'] + " " + song_dict['artist']
            search_response = youtube.search().list(
                part='snippet',
                q=song,
                maxResults=1
            ).execute()

            video_id = search_response['items'][0]['id']['videoId']

            youtube.playlistItems().insert(
                part='snippet',
                body={
                    'snippet': {
                        'playlistId': playlist_id,
                        'resourceId': {
                            'kind': 'youtube#video',
                            'videoId': video_id
                        }
                    }
                }
            ).execute()
            print(song, "inserted")
        except HttpError as e:
            print(f"Failed to add song: {song_dict}. Error: {e}")


liked_songs = get_spotify_liked_songs()
youtube = get_authenticated_service()
add_songs_to_youtube_playlist(youtube, "Spotify Liked Songs", liked_songs)

