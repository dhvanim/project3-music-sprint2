import * as React from 'react';
import SpotifyLogin from 'react-spotify-login';
import { Socket } from './Socket';

const onSuccess = (response) => {
  Socket.emit('new spotify user', {
    token: response.access_token,
  });
};

export default function SpotifyButton() {
  return (
    <div class="loginpage">
      <SpotifyLogin
        clientId="803918090e2d4726a922c0f05862e6e7"
        redirectUri="https://37baa11411bc449598a28599488f841f.vfs.cloud9.us-east-1.amazonaws.com/"
        onSuccess={onSuccess}
        scope="user-read-email user-top-read user-follow-read"
        className="spotifybutton"
      />
    </div>
  );
}
