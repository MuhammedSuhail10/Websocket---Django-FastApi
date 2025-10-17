This module provides the WebSocket server functionality for a FastAPI-based Ludo game backend. It manages real-time game interactions, including authentication, player connections, match state updates, and broadcasting game state to all players in a match.

## Features

- **WebSocket Endpoints**: Provides `/ws` endpoint for real-time gameplay.
- **Authentication**: Uses JWT tokens to authenticate users before establishing a WebSocket connection.
- **Connection Management**: Handles multiple active connections per user, supporting reconnection and broadcasting.
- **Match Participation Validation**: Ensures only users who are part of a match can connect and interact.
- **Game State Broadcasting**: Broadcasts real-time game state (dice rolls, turn changes, points, winner) to all match participants.
- **Turn Validation**: Ensures players move only on their turn and cannot impersonate other players.
- **Winning Logic**: Detects when a player wins and updates the match and player stats accordingly.
- **Points and Turn Management**: Updates player points and manages turn rotation based on dice results.
- **Cache Management**: Refreshes player profile cache on game completion.

## Major Classes and Functions

- **ConnectionManager**: Manages active WebSocket connections for users and matches, broadcasts messages.
- **authenticate_user**: Decodes JWT and retrieves the associated user from the database.
- **websocket_endpoint**: The main FastAPI WebSocket route for gameplay communication. Handles connection, validation, message processing, and broadcasting.
- **update_points**: Updates the points for each player and manages turn rotation.
- **match_result**: Handles end-of-game logic, updating player stats and match status.
- **is_winning_position**: Determines if a player has reached the winning position.

## Usage

1. **Connect to WebSocket**:  
   Connect to `/ws` providing a valid JWT in the `Authorization` header and `match_id` as a query parameter.
   ```
   ws://<host>/ws?match_id=<match_id>
   Headers:
     Authorization: Bearer <JWT_TOKEN>
   ```

2. **Message Protocol**:  
   - Send JSON messages with fields like `current_player_id`, `dice`, and points for each player.
   - Receive broadcast updates about the game state, including turn, dice value, and winner.

3. **Example Message Structure**:
   ```json
   {
     "current_player_id": 1,
     "dice": 5,
     "player1_point": [10, 20, 30, 40],
     "player2_point": [15, 25, 35, 45],
     "player3_point": [5, 15, 25, 35],
     "player4_point": [0, 10, 20, 30]
   }
   ```

## Requirements

- FastAPI
- Django (for ORM and cache)
- asgiref
- PyJWT (`jwt` library)
- Models: `Player`, `Matches`, `MatchStatus`

## Notes

- Ensure the Django models and settings are properly configured and imported.
- WebSockets are stateful; handle disconnects and reconnections with care.
- The game logic (like winning position and turn rotation) is implemented within this module but relies on the state provided by the Django backend.

## Security

- JWT tokens are mandatory for user authentication.
- Only users who are part of the specified match can connect and send actions for that match.
- Input validation is performed for dice values and turn ownership.

## Extending

- Support for additional game features or analytics can be added by extending broadcast messages or handling new message types.
- To support spectators or admin monitoring, modify `ConnectionManager` to handle observer roles.
