from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, APIRouter
from typing import Dict, List
import jwt
from django.conf import settings
import json
from asgiref.sync import sync_to_async
from Player.models import Player
from Matches.models import Matches, MatchStatus
from django.core.cache import cache

router = APIRouter()

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[int, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: int, message: dict = {}):
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)
        await manager.broadcast_to_user(message=message, user_id=user_id)

    def disconnect(self, websocket: WebSocket, user_id: int):
        if user_id in self.active_connections:
            self.active_connections[user_id].remove(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]

    async def broadcast_to_user(self, message: dict, user_id: int):
        if user_id in self.active_connections:
            disconnected = []
            for connection in self.active_connections[user_id]:
                try:
                    await connection.send_json(message)
                except WebSocketDisconnect:
                    disconnected.append(connection)
                except Exception as e:
                    print(f"Error broadcasting to user {user_id}: {e}")
                    disconnected.append(connection)
            
            # Clean up disconnected connections
            for conn in disconnected:
                self.active_connections[user_id].remove(conn)
            
            # Remove user if no active connections remain
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
    
    async def broadcast_to_match(self, message: dict, user_ids: List[int]):
        for user_id in user_ids:
            await self.broadcast_to_user(message, user_id)

manager = ConnectionManager()

async def authenticate_user(token):
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
        user_id = payload.get('user_id')
        if user_id and await Player.objects.filter(id=user_id).aexists():
            user = await Player.objects.aget(id=user_id)
            return user
        return None
    except jwt.ExpiredSignatureError:
        return None
    except Exception as e:
        return None

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    try:
        await websocket.accept()
        token = websocket.headers.get("Authorization")
        if not token:
            await websocket.close(code=4001, reason="No token provided in headers")
            return
        try:
            token = token.replace("Bearer ", "").strip()
            user = await authenticate_user(token)
            if not user:
                await websocket.close(code=4002, reason="Invalid user ID")
                return
            match_id = websocket.query_params.get("match_id")
            if not match_id:
                await websocket.close(code=4003, reason="No match_id provided")
                return
            match = await Matches.objects.aget(id=match_id)
            player1 = await sync_to_async(lambda: match.player1)()
            player2 = await sync_to_async(lambda: match.player2)()  
            player3 = await sync_to_async(lambda: match.player3)() if match.player3 else None
            player4 = await sync_to_async(lambda: match.player4)() if match.player4 else None
            if user not in [player1, player2, player3, player4]:
                await websocket.close(code=4004, reason="User not part of the match")
                return
            match_status = await MatchStatus.objects.aget(match__id=match_id)
            winner_id = None
            winner = await sync_to_async(lambda: match.winner)()
            if winner:
                winner_id = await sync_to_async(lambda: match.winner.player_id)()
            if match.status == "completed":
                message = {
                    "type": "play_update",
                    "data": {
                        "message": "Match finished",
                        "winner_id": winner_id
                    },
                }
            else:
                message = {
                    "type": "play_update",
                    "data": {
                        "match_id": match.id,
                        "current_player_id": await sync_to_async(lambda: match_status.current_player.player_id)(),
                        "dice": dice,
                        "player1_points": match_status.player1_points,
                        "player2_points": match_status.player2_points,
                        "player3_points": match_status.player3_points,
                        "player4_points": match_status.player4_points,
                        "winner_id": winner_id
                    },
                }
            await manager.connect(websocket, user.player_id, message=message)
            try:
                while True:
                    data_json = await websocket.receive_text()
                    data = json.loads(data_json)
                    match = await Matches.objects.aget(id=match_id)
                    match_status = await MatchStatus.objects.aget(match__id=match_id)
                    current_player_id = data.get("current_player_id")
                    dice = data.get("dice")

                    # Validations
                    if not current_player_id or dice is None:
                        await websocket.send_json({"error": "Missing required fields"})
                        continue
                    expected_player_id = await sync_to_async(lambda: match_status.current_player.player_id)()
                    if current_player_id != expected_player_id:
                        await websocket.send_json({"error": "Not your turn"})
                        continue
                    if current_player_id != user.player_id:
                        await websocket.send_json({"error": "Cannot play for another player"})
                        continue
                    try:
                        dice_value = int(dice)
                        if dice_value < 1 or dice_value > 6:
                            await websocket.send_json({"error": "Invalid dice value"})
                            continue
                    except (ValueError, TypeError):
                        await websocket.send_json({"error": "Invalid dice value"})
                        continue
                    player1_point = data.get("player1_point")
                    player2_point = data.get("player2_point")
                    player3_point = None
                    player4_point = None
                    if match.joined_players > 2:
                        player3_point = data.get("player3_point")
                        player4_point = data.get("player4_point")
                    winner = None

                    # Checking winning conditions
                    if is_winning_position(player1_point):
                        winner = await sync_to_async(lambda: match.player1.player_id)()
                        await match_result(match=match, current_player_id=winner)
                    elif is_winning_position(player2_point):
                        winner = await sync_to_async(lambda: match.player2.player_id)()
                        await match_result(match=match, current_player_id=winner)
                    elif match.joined_players > 2:
                        if player3_point and is_winning_position(player3_point):
                            winner = await sync_to_async(lambda: match.player3.player_id)()
                            await match_result(match=match, current_player_id=winner)
                        elif player4_point and is_winning_position(player4_point):
                            winner = await sync_to_async(lambda: match.player4.player_id)()
                            await match_result(match=match, current_player_id=winner)

                    # Update points and current player
                    await update_points(match_status, match, data, dice, current_player_id)
                    match = await Matches.objects.select_related('winner').aget(id=match_id)
                    match_status = await MatchStatus.objects.select_related('current_player').aget(match__id=match_id)
                    winner_id = None
                    winner = await sync_to_async(lambda: match.winner)()
                    if winner:
                        winner_id = await sync_to_async(lambda: winner.player_id)()
                    if match.status == "completed":
                        message = {
                            "type": "play_update",
                            "data": {
                                "message": "Match finished",
                                "winner_id": winner_id
                            },
                        }
                    else:
                        message = {
                            "type": "play_update",
                            "data": {
                                "match_id": match.id,
                                "current_player_id": await sync_to_async(lambda: match_status.current_player.player_id)(),
                                "dice": dice,
                                "player1_points": match_status.player1_points,
                                "player2_points": match_status.player2_points,
                                "player3_points": match_status.player3_points,
                                "player4_points": match_status.player4_points,
                                "winner_id": winner_id
                            },
                        }
                    player_ids = [
                        await sync_to_async(lambda: match.player1.player_id)(),
                        await sync_to_async(lambda: match.player2.player_id)(),
                    ]
                    if match.joined_players > 2:
                        player3 = await sync_to_async(lambda: match.player3)()
                        player4 = await sync_to_async(lambda: match.player4)()
                        if player3:
                            player_ids.append(await sync_to_async(lambda: player3.player_id)())
                        if player4:
                            player_ids.append(await sync_to_async(lambda: match.player4.player_id)())
                    await manager.broadcast_to_match(message, player_ids)
            except WebSocketDisconnect:
                manager.disconnect(websocket, user.player_id)
        except Exception as e:
            print(e)
            await websocket.close(code=4003, reason=str(e))
    except WebSocketDisconnect:
        if 'user_id' in locals():
            manager.disconnect(websocket, user.player_id)

async def update_points(match_status, match, data, dice, current_player_id):
    player3 = await sync_to_async(lambda: match.player3)()
    player4 = await sync_to_async(lambda: match.player4)()
    player1_point = data.get("player1_point")
    player2_point = data.get("player2_point")
    player1_id = await sync_to_async(lambda: match.player1.player_id)()
    player2_id = await sync_to_async(lambda: match.player2.player_id)()
    player3_id = None
    player4_id = None
    match_status.player1_points = player1_point
    match_status.player2_points = player2_point
    if match.joined_players > 2:
        player3_point = data.get("player3_point")
        player4_point = data.get("player4_point")
        if player3:
            player3_id = await sync_to_async(lambda: match.player3.player_id)()
            match_status.player3_points = player3_point
        if player4:
            player4_id = await sync_to_async(lambda: player4.player_id)()
            match_status.player4_points = player4_point
    if dice < 6:
        if current_player_id == player1_id:
                match_status.current_player = await sync_to_async(lambda: match.player2)()
        elif current_player_id == player2_id:
                if match.joined_players > 2 and player3:
                    next_player = player3
                else:
                    next_player = await sync_to_async(lambda: match.player1)()
                match_status.current_player = next_player
        elif player3_id and current_player_id == player3_id:
                if player4:
                    match_status.current_player = player4
                else:
                    match_status.current_player = await sync_to_async(lambda: match.player1)()
        elif player4_id and current_player_id == player4_id:
                match_status.current_player = await sync_to_async(lambda: match.player1)()
    await match_status.asave()

async def match_result(match, current_player_id):
    game_type = await sync_to_async(lambda: match.game.type)()
    winner = await Player.objects.aget(player_id=current_player_id)
    if game_type == "bonus":
        winner.bonus += match.winning_amount
    else:
        winner.withdrawable_coin += (match.winning_amount - match.game.fee)
        winner.coin += match.winning_amount
    await winner.asave()
    await sync_to_async(cache.delete)(f"player_profile_{winner.player_id}")
    match.winner = winner
    match.status = "completed"
    await match.asave()

def is_winning_position(points):
    return points == [56, 56, 56, 56]