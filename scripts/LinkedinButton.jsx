import * as React from 'react';
import { Socket } from './Socket';

function handleSubmit(event) {
    // TODO replace with name from oauth
    let name = "John Doe";
    Socket.emit('new linkedin user', {
        'name': name,
    });
    
    console.log('Sent the name ' + name + ' to server!');
}

export function LinkedinButton() {
    return (
            <button onClick={handleSubmit}>Log in with LinkedIn!</button>
    );
}
