import * as React from 'react';
import SpotifyLogin from 'react-spotify-login';
import { NavLink } from 'react-router-dom';
import { Socket } from './Socket';

const onSuccess = (response) => {
  Socket.emit('new spotify user', {
    token: response.access_token,
  });
};

export default function SpotifyButton() {
  return (
    <div className="loginpage">
      <div className="loginblock">
        <h1> Musikalee </h1>

        <SpotifyLogin
          clientId="803918090e2d4726a922c0f05862e6e7"
          redirectUri="https://musikalee.herokuapp.com/"
          onSuccess={onSuccess}
          scope="user-read-email user-top-read user-follow-read user-read-currently-playing"
          className="spotifybutton"
          buttonText="Spotify Log In"
          callBack
        />
        <br />
        <div className="landinglink">
          <NavLink to="/about"> About Us </NavLink>
        </div>
      </div>

    </div>
  );
}
