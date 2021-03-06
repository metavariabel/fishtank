import sprites
import random
import math
import cards
import metastates

class GameState:
    def __init__(self, board_stiles, gameview, meta_state):
        self.stiles = board_stiles
        self.tiles = list(map(lambda s: s.tile, self.stiles))
        self.gameview = gameview
        self.z_mid = list(filter(lambda z: z.name == "Constructs", self.gameview.z_layers))[0]
        self.z_front = list(filter(lambda z: z.name == "Front", self.gameview.z_layers))[0]
        self.meta_state = meta_state
    
    def ActivateState(self):
        pass

    def DeactivateState(self):
        pass

class Player:
    def __init__(self, color, name):
        self.color = color
        self.name = name
        self.cards = cards.LandCards()
        self.dev_cards = cards.DevelopmentCards()
        self.score = 0
        self.ai = None

class Scores:
    def __init__(self, players):
        self.players = players
        self.towns = list()
        self.player_with_longest_road = None
        self.player_with_largest_army = None
    
    def RandomStartingPlayer(self):
        starting_player = self.players[random.randint(0, len(self.players) - 1)]
        while self.players[0] != starting_player:
            self.players.append(self.players.pop(0))
        return starting_player

    # work in progress
    def CountScores(self):
        for player in self.players:
            player.score = len(list(filter(lambda town: town.player == player, self.towns))) + \
                2 * len(list(filter(lambda town: town.is_city and town.player == player, self.towns))) + \
                len(list(filter(lambda card: card == "1", player.dev_cards)))

class StateTools:

    def ProximalRoadsBelongsToThisPlayer(tile, h, j, player_color):
        return tile.Road(h) and tile.Road(h).color == player_color \
            or tile.Road(j) and tile.Road(j).color == player_color

    def ProximalTownsBelongsToThisPlayer(tile, i, j, optional_town, player_color):
        if optional_town:
            return  tile.corners[i].town and tile.corners[i].town and tile.corners[i].town.player_color == player_color and tile.corners[i].town == optional_town \
                or tile and tile.corners[j].town and tile.corners[j].town.player_color == player_color and tile.corners[j].town == optional_town
        return not tile.corners[i].town is None and not tile.corners[i].town is None and tile.corners[i].town.player_color == player_color \
                or not tile is None and not tile.corners[j].town is None and tile.corners[j].town.player_color == player_color
    
    def ProximalRoadAndNotCloseToTown(corner, player_color):
        # Check if there is a road for this player adjacent to the target location.
        tile = corner.tile
        target = corner.direction_int
        (i, j) = (target - 1, target)

        if not StateTools.TwoRoadsNextToTown(tile, target):
            return False

        # Either there needs to be a road at i or j from this tile:
        if tile.Road(i) and tile.Road(i).color == player_color or \
            tile.Road(j) and tile.Road(j).color == player_color:
            return True

        # Or one of the neighbors from this corner at location target - 3:
        (neighbor_tile, nt) = StateTools.GetAdjacentTile(tile, i, j)
        # nt is now the target town location seen from the neighbor tile.
        if neighbor_tile:
            # The neighbor town needs a road at location nt or nt - 1:
            if neighbor_tile.Road(nt) and neighbor_tile.Road(nt).color == player_color or \
                neighbor_tile.Road(nt - 1) and neighbor_tile.Road(nt - 1).color == player_color:
                return True

        return False

    def GetAdjacentTile(tile, i, j):
        (neighbor_tile, nt) = (tile.edges[i], i - 3)
        if not neighbor_tile:
            (neighbor_tile, nt) = (tile.edges[j], j - 3)
        return (neighbor_tile, nt)
    
    def CornerNotNextToTown(corner):
        return not any(map(lambda neighbor: neighbor.HasTown(), corner.neighbor_corners))

    def CornerNextToTown(tile, i):
        return tile.corners[i - 1] and tile.corners[i - 1].HasTown() or \
            tile.corners[i + 1] and tile.corners[i + 1].HasTown()
    
    # Returns True if town location is valid.
    def TwoRoadsNextToTown(tile, town_id):
        # When placing a town on a tile next to a road,
        # there cannot be a town at an adjacent corner.
        
        # The basic adjacent corners are:
        (h, j) = (town_id - 1, town_id + 1 if town_id < len(tile.corners) else 0)
        if tile.corners[h] and tile.corners[h].HasTown() or \
            tile.corners[j] and tile.corners[j].HasTown():
            return False

        # Or, one adjacent tile has a town at location nt - 1 or nt + 1
        (neighbor_tile, nt) = StateTools.GetAdjacentTile(tile, town_id, j)
        if neighbor_tile and StateTools.CornerNextToTown(neighbor_tile, nt):
            return False
        return True

class PlaceTownState(GameState):
    def __init__(self, board_stiles, gameview, player, meta_state, must_be_adjacent, cancel_action_key):
        super().__init__(board_stiles, gameview, meta_state)
        self.player = player
        
        self.pointer = None
        self.status_text = None
        self.placed_town = None
        self.must_be_adjacent = must_be_adjacent
        self.cancel_action_key = cancel_action_key
    
    def ActivateState(self):
        self.pointer = sprites.SPointer()
        self.gameview.AddSprite(self.pointer, self.z_front)

        self.status_text = sprites.Text('{} please place a town'.format(self.player.name), 'Comic Sans MS', 30)
        self.status_text.color = self.player.color
        (self.status_text.x, self.status_text.y) = (230, 3)
        self.gameview.all_texts.append(self.status_text)

    def update(self):

        if self.cancel_action_key and self.cancel_action_key.cancel:
            self.placed_town = None
            self.CleanupState()
            self.player.cards.brick += 1
            self.player.cards.wood += 1
            self.player.cards.sheep += 1
            self.player.cards.wheat += 1
            self.meta_state.NextState(self)
            return

        stiles_hovering = [s for s in self.stiles if s.hover]
        if len(stiles_hovering) > 0:
            stile = stiles_hovering[0]
            self.pointer.hide = False

            # set pointer location to the closest available corner
            distances = map(lambda corner: (corner.distance_to_point(self.gameview.mouse_x, self.gameview.mouse_y), corner), \
                filter(lambda corner: corner, stile.tile.corners))
            distances = sorted(distances, key=lambda p: p[0])
            if len(distances) > 0:
                closest_corner = distances[0][1]
                self.pointer.set_position(closest_corner.position)
                # self.status_text.update_text("{} [] {}, {} corners".format(
                #     stile.tile.name, stile.tile.value,
                #     sum(map(lambda c: 0 if c is None else 1, stile.tile.corners))))
                
                # clicked?
                if stile.clicked:
                    if self.LocationAcceptable(stile, closest_corner):
                        self.gameview.AddSprite(sprites.STown(self.player.color, closest_corner), self.z_mid)
                        self.CleanupState()
                        self.placed_town = closest_corner.town
                        self.meta_state.NextState(self)
                    else:
                        self.status_text.text = "Oh no, location not legal. try again pls"
        else:
            self.pointer.hide = True
            # self.status_text.update_text('-')

    def CleanupState(self):
        self.gameview.RemoveSprite(self.pointer, self.z_front)
        self.gameview.all_texts.remove(self.status_text)

    def LocationAcceptable(self, stile, corner):
        # Not acceptable if there already is a town in this corner.
        if corner.HasTown():
            return False

        if not self.must_be_adjacent:
            return StateTools.CornerNotNextToTown(corner)
        
        # Only acceptable if there is an adjacent road
        return StateTools.ProximalRoadAndNotCloseToTown(corner, self.player.color)
        
class PlaceRoadState(GameState):
    def __init__(self, board_stiles, gameview, player, meta_state, preceding_town_state, cancel_action_key):
        super().__init__(board_stiles, gameview, meta_state)
        self.player = player
        
        self.pointer = None
        self.status_text = None

        # The optional town can be provided to let the game state know this is the opening phase of the game.
        # The road then needs to be placed adjacent to this town.
        self.preceding_town_state = preceding_town_state
        self.optional_town = None
        self.cancel_action_key = cancel_action_key
    
    def ActivateState(self):
        self.pointer = sprites.SPointer()
        self.gameview.AddSprite(self.pointer, self.z_front)

        self.optional_town = self.preceding_town_state.placed_town if self.preceding_town_state else None

        self.status_text = sprites.Text('{} please place a road'.format(self.player.name), 'Comic Sans MS', 30)
        self.status_text.color = self.player.color
        (self.status_text.x, self.status_text.y) = (230, 3)
        self.gameview.all_texts.append(self.status_text)        

    def DistanceToPoint(self, x, y, p2):
        return math.sqrt( (x - p2[0]) ** 2 + (y - p2[1]) ** 2)

    def update(self):
        if self.cancel_action_key and self.cancel_action_key.cancel:
            self.CleanupState()
            self.player.cards.brick += 1
            self.player.cards.wood += 1
            self.meta_state.NextState(self)
            return

        stiles_hovering = [s for s in self.stiles if s.hover]
        if len(stiles_hovering) > 0:
            stile = stiles_hovering[0]
            self.pointer.hide = False

            # set pointer location to the closest available corner
            distances = map(lambda edge_position: (self.DistanceToPoint(self.gameview.mouse_x, self.gameview.mouse_y, edge_position[1]), edge_position), \
                map(lambda i: (i, stile.edge_positions[i]), \
                    filter(lambda i: self.StileEdgeAllowsRoad(stile, i), list(range(0, 6)))))
            distances = sorted(distances, key=lambda p: p[0])
            if len(distances) > 0:
                closest_edge_id = distances[0][1][0]
                closest_position = distances[0][1][1]
                self.pointer.set_position(closest_position)
                
                # clicked?
                if stile.clicked:
                    if self.LocationAcceptable(stile, closest_edge_id):
                        self.gameview.AddSprite(sprites.SRoad(stile.tile, self.player.color, closest_edge_id), self.z_mid)
                        self.CleanupState()
                        self.meta_state.NextState(self)
                    else:
                        self.status_text.text = "Oh no, location not legal. try again pls"
        else:
            self.pointer.hide = True
            # self.status_text.update_text('-')
    def CleanupState(self):
        self.gameview.RemoveSprite(self.pointer, self.z_front)
        self.gameview.all_texts.remove(self.status_text)

    def LocationAcceptable(self, stile, edge_id):
        return stile.tile.roads[edge_id] is None
    
    def StileEdgeAllowsRoad(self, stile, i):
        # i is road to place, h and j are adjacent edges.
        (h, j) = (i - 1 if i > 0 else 5, i + 1 if i < 5 else 0)
        # neighboring tile also has adjacent edges hn and jn.
        # i_n is the edge i but on the neighbor, so ~ i + 3.
        neighbor_tile = stile.tile.edges[i]
        (hn, i_n, jn) = (h + 3 if h < 3 else h - 3, i + 3 if i < 3 else i - 3, j + 3 if j < 3 else j - 3)
        
        # Not ok to place road if there already is one there.
        if stile.tile.roads[i] is not None or not neighbor_tile is None and neighbor_tile.roads[i_n] is not None:
            return False

        # In the start of the game, placement is only allowed next to the town just placed.
        if self.optional_town:
            return stile.tile.corners[i].town == self.optional_town or \
                stile.tile.corners[j].town == self.optional_town
            # return stile.tile.corners[h].town == self.optional_town or stile.tile.corners[j] == self.optional_town

        # Ok to place road next to town belonging to this player
        if StateTools.ProximalTownsBelongsToThisPlayer(stile.tile, i, j, self.optional_town, self.player.color) or \
            not neighbor_tile is None and StateTools.ProximalTownsBelongsToThisPlayer(neighbor_tile, i_n, jn, self.optional_town, self.player.color):
            return True
        
        # proximity to player's other roads then decides if it's ok or not.
        return StateTools.ProximalRoadsBelongsToThisPlayer(stile.tile, h, j, self.player.color) or \
            (not neighbor_tile is None and StateTools.ProximalRoadsBelongsToThisPlayer(neighbor_tile, hn, jn, self.player.color))

class PlayerRollDiceState(GameState):
    def __init__(self, board_stiles, gameview, meta_state):
        super().__init__(board_stiles, gameview, meta_state)
    
    def ActivateState(self):
        pass

class PlayerMainPhaseState(GameState):
    def __init__(self, board_stiles, gameview, meta_state, player, keys, cancel_action_key):
        super().__init__(board_stiles, gameview, meta_state)
        self.status_text = None
        self.player = player
        self.keys = keys
        self.rolled = False
        self.rolled_value = 0
        self.cancel_action_key = cancel_action_key
        self.action_underway = False
    
    def ActivateState(self):
        if self.status_text:
            self.status_text.removed = False
        else:
            self.status_text = sprites.Text('{}''s turn! Spacebar = roll dice, b = use a knight card and move bandits.'.format(self.player.name), 'Comic Sans MS', 20)
            self.status_text.color = self.player.color
            self.gameview.all_texts.append(self.status_text)
        
        (self.status_text.x, self.status_text.y) = (30, 30)
        self.meta_state.current_hand_text.color = self.player.color
        self.PrintPlayerHand()

    def DeactivateState(self):
        if self.status_text:
            self.status_text.y -= 20
            self.status_text.update_text("{0} rolled {1}. Turn over.".format(self.player.name, self.rolled_value))
        self.rolled = False

    def UpdatePlayerState(self):
        self.PrintPlayerHand()
        self.PrintPlayerOptions()

    def PrintPlayerOptions(self):
        self.status_text.update_text("{0} rolled {1}! Press N for next player. {2}".format(self.player.name, self.rolled_value, self.player.cards.PrintPossibilities()))

    def PrintPlayerHand(self):
        new_text = "{0}'s hand: {1}{2}{3}".format(self.player.name, self.player.cards.Print(), "\r\n", self.player.dev_cards.Print())
        self.meta_state.current_hand_text.update_text(new_text)

    def update(self):
        
        if self.action_underway:
            self.UpdatePlayerState()

        if not self.rolled and not self.keys.next_player:
            
            # player turn: roll the dice or play knight (if no knight available, roll automatically)
            if self.player.dev_cards.knights == 0 or self.keys.roll:
                self.rolled_value = self.RollDice()
                self.UpdatePlayerState()
                self.rolled = True
        
        if self.rolled:

            # build something
            if self.player.cards.CanBuildRoad() and self.keys.build_road:
                self.player.cards.brick -= 1
                self.player.cards.wood -= 1
                self.meta_state.TriggerPlayerActionState(PlaceRoadState(self.stiles, self.gameview, self.player, self.meta_state, None, self.cancel_action_key))
                self.action_underway = True
                self.UpdatePlayerState()
            if self.player.cards.CanBuildTown() and self.keys.build_town:
                self.player.cards.brick -= 1
                self.player.cards.wood -= 1
                self.player.cards.wheat -= 1
                self.player.cards.sheep
                self.meta_state.TriggerPlayerActionState(PlaceTownState(self.stiles, self.gameview, self.player, self.meta_state, True, self.cancel_action_key))
                self.UpdatePlayerState()
                self.action_underway = True
            if self.player.cards.CanBuildCity() and self.keys.build_city:
                self.player.cards.stone -= 3
                self.player.cards.wheat -= 2
                #self.meta_state.TriggerPlayerActionState(ChooseCityState(self.stiles, self.gameview, self.player, self, None))
                self.UpdatePlayerState()
                self.action_underway = True
            if self.player.cards.CanBuyDevCard() and self.keys.buy_development_card:
                self.player.cards.stone -= 1
                self.player.cards.wheat -= 1
                self.player.cards.sheep -= 1
                # buy dev card (not implemented)
                self.UpdatePlayerState()
                self.action_underway = True

            # use dev cards


            if self.keys.next_player:
                self.meta_state.NextState(self)

    def RollDice(self):
        value = self.meta_state.rolled_dice = random.randint(1, 6) + random.randint(1, 6)

        # Hand out land cards
        if value != 7:
            for stile in filter(lambda stile: stile.tile.value == value, self.stiles):
                corners_with_towns = list(filter(lambda corner: corner.town, stile.tile.corners))
                if len(corners_with_towns) > 0:
                    card = cards.LandCard(stile.tile.type)
                    for corner in corners_with_towns:
                        player = self.meta_state.GetPlayer(corner.town.player_color)
                        player.cards.AddCardToHand(card)
                        if corner.town.is_city:
                            player.cards.AddCardToHand(card)
        return value

class PlayerMoveBanditState(GameState):
    def __init__(self, board_stiles, gameview, meta_state, player, rolled_seven):
        super().__init__(board_stiles, gameview, meta_state)
    
        self.status_text = None
        self.rolled_seven = rolled_seven
        self.player = player
    
    def ActivateState(self):
        self.status_text = sprites.Text('{} chooses another location for the bandits!'.format(self.player.name), 'Comic Sans MS', 30)
        if self.rolled_seven:
            self.status_text = sprites.Text('{} rolled a 7 and chooses another location for the bandits!'.format(self.player.name), 'Comic Sans MS', 30)
        self.status_text.color = self.player.color
        (self.status_text.x, self.status_text.y) = (230, 3)
        self.gameview.all_texts.append(self.status_text)

class PlayerStealCardState(GameState):
    def __init__(self, board_stiles, gameview, meta_state, player):
        super().__init__(board_stiles, gameview, meta_state)
        self.status_text = None
        self.player = player
    
    def ActivateState(self):
        self.status_text = sprites.Text('{} chooses a player to steal a card from.'.format(self.player.name), 'Comic Sans MS', 30)
        self.status_text.color = self.player.color
        (self.status_text.x, self.status_text.y) = (230, 3)
        self.gameview.all_texts.append(self.status_text)
