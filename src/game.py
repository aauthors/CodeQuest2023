import random

import comms
from object_types import ObjectTypes

import sys
import math


class Game:
    """
    Stores all information about the game and manages the communication cycle.
    Available attributes after initialization will be:
    - tank_id: your tank id
    - objects: a dict of all objects on the map like {object-id: object-dict}.
    - width: the width of the map as a floating point number.
    - height: the height of the map as a floating point number.
    - current_turn_message: a copy of the message received this turn. It will be updated everytime `read_next_turn_data`
        is called and will be available to be used in `respond_to_turn` if needed.
    """
    def __init__(self):

        tank_id_message: dict = comms.read_message()
        
        self.tank_id = tank_id_message["message"]["your-tank-id"]
        self.enemy_tank_id = tank_id_message["message"]["enemy-tank-id"]
        self.current_turn_message = None
        self.last_path_requested = None

        self.tick = 0 # tick counter

        # We will store all game objects here
        self.objects = {}

        self.walls = []

        next_init_message = comms.read_message()
        while next_init_message != comms.END_INIT_SIGNAL:
            # At this stage, there won't be any "events" in the message. So we only care about the object_info.
            object_info: dict = next_init_message["message"]["updated_objects"]

            # Store them in the objects dict
            self.objects.update(object_info)

            # Read the next message
            next_init_message = comms.read_message()

        # We are outside the loop, which means we must've received the END_INIT signal

        # Let's figure out the map size based on the given boundaries

        # Read all the objects and find the boundary objects
        boundaries = []
        for game_object in self.objects.values():
            if game_object["type"] == ObjectTypes.BOUNDARY.value:
                boundaries.append(game_object)
            #Append walls & desctructible walls to our wall array
            elif game_object["type"] == ObjectTypes.WALL.value:
                self.walls.append(game_object)
            elif game_object["type"] == ObjectTypes.DESTRUCTIBLE_WALL.value:
                self.walls.append(game_object)

        print(f"MY_WALLS: [{self.walls}]", file=sys.stderr)

        # The biggest X and the biggest Y among all Xs and Ys of boundaries must be the top right corner of the map.

        # Let's find them. This might seem complicated, but you will learn about its details in the tech workshop.
        biggest_x, biggest_y = [
            max([max(map(lambda single_position: single_position[i], boundary["position"])) for boundary in boundaries])
            for i in range(2)
        ]

        self.width = biggest_x
        self.height = biggest_y

    def read_next_turn_data(self):
        """
        It's our turn! Read what the game has sent us and update the game info.
        :returns True if the game continues, False if the end game signal is received and the bot should be terminated
        """
        # Read and save the message
        self.current_turn_message = comms.read_message()

        if self.current_turn_message == comms.END_SIGNAL:
            return False

        # Delete the objects that have been deleted
        # NOTE: You might want to do some additional logic here. For example check if a powerup you were moving towards
        # is already deleted, etc.
        for deleted_object_id in self.current_turn_message["message"]["deleted_objects"]:
            try:
                del self.objects[deleted_object_id]
            except KeyError:
                pass

        # Update your records of the new and updated objects in the game
        # NOTE: you might want to do some additional logic here. For example check if a new bullet has been shot or a
        # new powerup is now spawned, etc.
        self.objects.update(self.current_turn_message["message"]["updated_objects"])

        return True

    def respond_to_turn(self):
        """
        This is where you should write your bot code to process the data and respond to the game.
        """
        self.tick += 1
        to_post = {}
        path_updated = False

        # to_post.update({"shoot": random.uniform(0, random.randint(1, 360))})

        # Write your code here... For demonstration, this bot just shoots randomly every turn.
        # to_post.update({"shoot": random.uniform(0, random.randint(1, 360))}) 

        #print(f"new position: [{self.objects}]", file=sys.stderr)
        my_tank = self.objects[self.tank_id]
        my_tank_posx, my_tank_posy = my_tank["position"] 
        enemy_tank = self.objects[self.enemy_tank_id] #Enemy tank
        enemy_tank_pos = enemy_tank["position"]

        # STRATS
        # TODO: avoid boundary
        boundary = self.objects["closing_boundary-1"]
        bound_rangex_left = boundary["position"][0][0]+boundary["velocity"][0][0] + 50
        bound_rangex_right = boundary["position"][2][0]+boundary["velocity"][2][0] - 50 
        bound_rangey_bottom = boundary["position"][1][1]+boundary["velocity"][1][1] + 50
        bound_rangey_top = boundary["position"][3][1]+boundary["velocity"][3][1] - 50

        if (my_tank_posx < bound_rangex_left or my_tank_posx > bound_rangex_right or my_tank_posy < bound_rangey_bottom or my_tank_posy > bound_rangey_top):
            new_pathx = round(random.uniform(bound_rangex_left, bound_rangex_right), 1)
            new_pathy = round(random.uniform(bound_rangey_bottom, bound_rangey_top), 1)
            print(f"new position: [{new_pathx},{new_pathy}]", file=sys.stderr)
            self.last_path_requested = [new_pathx, new_pathy]
            to_post.update({"path": [new_pathx, new_pathy]})
            path_updated = True
        
        # TODO: avoid approaching bullets
        my_tank_xrange = [my_tank_posx-10, my_tank_posx+10]
        my_tank_yrange = [my_tank_posy-10, my_tank_posy+10]
        for key in self.objects.keys():
            if self.objects[key]["type"] == 2: # check it is of bullet type
                bullet = self.objects[key]
                bullet_posx = bullet["position"][0] + 2*bullet["velocity"][0]
                bullet_posy = bullet["position"][1] + 2*bullet["velocity"][1]
                if not path_updated and (bullet_posx > my_tank_xrange[0] and bullet_posx < my_tank_xrange[1]) and (bullet_posy > my_tank_yrange[0] and bullet_posy < my_tank_yrange[1]):
                    bullet_angle = math.atan2(2*bullet["velocity"][0], 2*bullet["velocity"][1])
                    y_distance = 200*math.tan(bullet_angle)
                    to_post.update({"path": [my_tank_posx+200, my_tank_posy+y_distance]})
                    path_updated = True


        # TODO: move towards powerups
        if not path_updated and (my_tank["hp"] <= 3):
            powerup_positions = []
            for key in self.objects.keys():
                if self.objects[key]["type"] == 7: 
                    powerup_positions.append(self.objects[key]["position"])

            min_pos_x, min_pos_y = enemy_tank_pos
            min_dist = float('inf')
            for pposx, pposy in powerup_positions:
                if (abs(pposx - my_tank_posx)**2) + (abs(pposy - my_tank_posy) ** 2) < min_dist:
                    min_dist = (abs(pposx - my_tank_posx)**2) + (abs(pposy - my_tank_posy) ** 2)
                    min_pos_x, min_pos_y = pposx, pposy
            to_post.update({"path": [min_pos_x, min_pos_y]})
            path_updated = True

            distance = abs(my_tank_posx - enemy_tank_pos[0]) + abs(my_tank_posy) - abs(enemy_tank_pos[1])
            angle = None
            if distance < 500:
                x1 = my_tank_posx
                y1 = my_tank_posy
                x2 = enemy_tank_pos[0]
                y2 = enemy_tank_pos[1]
                
                angle = math.atan2(y2 - y1, x2 - x1) * 180 / math.pi
                
                to_post.update({"shoot": angle})
        
        # TODO: go to enemy and shoot
        if not path_updated and self.last_path_requested is None or self.last_path_requested != enemy_tank_pos:
            
            noWallX = True
            noWallY = True

            for wall in self.walls:
                
                w_x, w_y = wall["position"]
                en_x, en_y = enemy_tank_pos

                if (en_x > w_x - 9) or (en_x < w_x + 9):
                    noWallX = False
                if (en_y > w_y - 9) or (en_y < w_y + 9):
                    noWallY = False
            
            if noWallX:
                to_post.update({"path": [en_x, my_tank_posy]})
                self.last_path_requested = [en_x, my_tank_posy]
                path_updated = True
            elif noWallY:
                to_post.update({"path": [my_tank_posx, en_y]})
                self.last_path_requested = [my_tank_posx, en_y]
                path_updated = True

            
 
        
        distance = abs(my_tank_posx - enemy_tank_pos[0]) + abs(my_tank_posy) - abs(enemy_tank_pos[1])
            
        angle = None
        if distance < 500:
            x1 = my_tank_posx
            y1 = my_tank_posy
            x2 = enemy_tank_pos[0]
            y2 = enemy_tank_pos[1]
            
            angle = math.atan2(y2 - y1, x2 - x1) * 180 / math.pi
            
            to_post.update({"shoot": angle})





        print(f"Posted Message ({self.tick}): [{to_post}]", file=sys.stderr)
        comms.post_message(to_post)