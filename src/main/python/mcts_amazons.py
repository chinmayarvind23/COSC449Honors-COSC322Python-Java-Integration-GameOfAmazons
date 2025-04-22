# pip install py4j and run this file first and then run COSC322GamePlayer.java and run another instance of COSC322GamePlayer.java that have both joined the same game room
import math, random, threading
from py4j.clientserver import ClientServer, JavaParameters, PythonParameters

# queen current pos, queen new pos, shot arrow pos
class Action:
    def __init__(self, queen_curr, queen_new, arrow_shot, id_):
        self.queen_curr, self.queen_new, self.arrow_shot, self.id = queen_curr, queen_new, arrow_shot, id_
    def getQueenPositionCurrent(self): return self.queen_curr
    def getQueenPositionNew(self):     return self.queen_new
    def getArrowPosition(self):        return self.arrow_shot
    def getId(self):                   return self.id

# Getting possible actions
class ActionFactory:
    directions = [(1,0),(1,1),(1,-1),(-1,0),(-1,1),(-1,-1),(0,-1),(0,1)]
    def __init__(self, state, player):
        self.state = [row[:] for row in state]
        self.player = player
        self._next_id = 0

    def get_actions(self):
        actions = []
        for x in range(10):
            for y in range(10):
                if self.state[x][y] == self.player:
                    actions.extend(self._queen_moves(x,y))
        return actions

    def _queen_moves(self, x, y):
        queen_moves = []
        for diff_x,diff_y in ActionFactory.directions:
            step = 1
            while True:
                new_x,new_y = x+diff_x*step, y+diff_y*step
                if not (0 <= new_x < 10 and 0 <= new_y < 10 and self.state[new_x][new_y]==0):
                    break
                queen_moves += self._arrow_shots([x,y],[new_x,new_y])
                step += 1
        return queen_moves

    def _arrow_shots(self, queen_curr, queen_new):
        board_state = [row[:] for row in self.state]
        board_state[queen_curr[0]][queen_curr[1]] = 0
        board_state[queen_new[0]][queen_new[1]] = self.player
        shots = []
        for diff_x,diff_y in ActionFactory.directions:
            step = 1
            while True:
                arrow_x,arrow_y = queen_new[0]+diff_x*step, queen_new[1]+diff_y*step
                if not (0 <= arrow_x < 10 and 0 <= arrow_y < 10 and board_state[arrow_x][arrow_y]==0):
                    break
                self._next_id += 1
                shots.append(Action(queen_curr,queen_new,[arrow_x,arrow_y],self._next_id))
                step += 1
        return shots

# State in MCTS
class Node:
    def __init__(self, st, playerType, queen_curr, queen_new, arrow_shot, id_):
        self.state       = [row[:] for row in st]
        self.playerType  = playerType
        self.queenCurrent= queen_curr
        self.queenNew    = queen_new
        self.arrow       = arrow_shot
        self.id          = id_
        self.rollouts    = 1
        self.totalWins   = 0
        self.punishment  = 0.4
        self.ucb1Score   = float('inf')
        self.children    = []
        self.currentChildren = {}
        self.terminal    = -1

    def avg_win(self): return self.totalWins/self.rollouts
    def update_ucb1(self, parentRollouts):
        self.ucb1Score = self.avg_win() + math.sqrt(2)*math.sqrt(math.log(parentRollouts)/self.rollouts) - self.punishment

# Prunes MCTS tree
class NodeChildrenGenerator:
    @staticmethod
    def generate(node):
        node.children.clear()
        actions = ActionFactory(node.state, node.playerType).get_actions()
        valid_action_ids = {a.getId() for a in actions}
        node.currentChildren = {
            id_: child_node
            for id_, child_node in node.currentChildren.items()
            if id_ in valid_action_ids
        }
        if node.terminal == -1:
            if not actions:
                node.terminal = 2 if node.playerType==1 else 1
            else:
                node.terminal = 0
        if node.terminal!=0:
            return
        for a in actions:
            if a.getId() in node.currentChildren:
                child_node = node.currentChildren[a.getId()]
            else:
                board_state = [r[:] for r in node.state]
                q_curr, q_new, arrow_shot = a.getQueenPositionCurrent(), a.getQueenPositionNew(), a.getArrowPosition()
                board_state[q_curr[0]][q_curr[1]] = 0
                board_state[q_new[0]][q_new[1]] = node.playerType
                board_state[arrow_shot[0]][arrow_shot[1]] = 7
                child_node = Node(board_state, 2 if node.playerType==1 else 1, q_curr, q_new, arrow_shot, a.getId())
                node.currentChildren[a.getId()] = child_node
            node.children.append(child_node)

# Picks a node to rollout
class RolloutManager:
    @staticmethod
    def rollout(node, parentRollouts):
        NodeChildrenGenerator.generate(node)
        if node.terminal!=0:
            return node.terminal
        node.rollouts += 1
        actions = ActionFactory(node.state, node.playerType).get_actions()
        action_chosen = random.choice(actions)
        chosen_action_id = action_chosen.getId()
        if chosen_action_id in node.currentChildren:
            recursor_child_node = node.currentChildren[chosen_action_id]
        else:
            board_state = [r[:] for r in node.state]
            q_curr, q_new, arrow_shot = action_chosen.getQueenPositionCurrent(), action_chosen.getQueenPositionNew(), action_chosen.getArrowPosition()
            board_state[q_curr[0]][q_curr[1]] = 0
            board_state[q_new[0]][q_new[1]] = node.playerType
            board_state[arrow_shot[0]][arrow_shot[1]] = 7
            recursor_child_node = Node(board_state, 2 if node.playerType==1 else 1, q_curr,q_new,arrow_shot, chosen_action_id)
            node.currentChildren[chosen_action_id] = recursor_child_node
        winner = RolloutManager.rollout(recursor_child_node, node.rollouts)
        if winner == node.playerType:
            node.totalWins += 1
        else:
            node.punishment += 0.3
        node.update_ucb1(parentRollouts)
        return winner

# Factor in opponent move
class OpponentValidator:
    @staticmethod
    def validate(node, queen_curr, queen_new, arrow_shot):
        def map(pos):
            return [10 - pos[0], pos[1] - 1]

        queen_curr_mapped = map(queen_curr)
        queen_new_mapped = map(queen_new)
        arrowshot_mapped = map(arrow_shot)
        actions = ActionFactory(node.state, node.playerType).get_actions()
        for a in actions:
            if (a.getQueenPositionCurrent() == queen_curr_mapped
                and a.getQueenPositionNew()     == queen_new_mapped
                and a.getArrowPosition()        == arrowshot_mapped):
                if a.getId() in node.currentChildren:
                    node.__dict__.update(node.currentChildren[a.getId()].__dict__)
                else:
                    board_state = [r[:] for r in node.state]
                    board_state[queen_curr_mapped[0]][queen_curr_mapped[1]] = 0
                    board_state[queen_new_mapped[0]][queen_new_mapped[1]] = node.playerType
                    board_state[arrowshot_mapped[0]][arrowshot_mapped[1]] = 7
                    child_node = Node(board_state, 2 if node.playerType==1 else 1, queen_curr_mapped, queen_new_mapped, arrowshot_mapped, a.getId())
                    node.__dict__.update(child_node.__dict__)
                NodeChildrenGenerator.generate(node)
                return True
        return False


# Creating methods that Java can call and access through Py4J gateway created in COSC322GamePlayer.java file
class MCTSBridge:
    def __init__(self):
        self.root = None
        self.numThreads = 1
        self.gateway = None

    def setCurrentNode(self, boardState, playerId):
        python_board_state = []
        for java_row in boardState:
            python_board_state.append([int(cell) for cell in java_row])
        self.root = Node(python_board_state, playerId, None, None, None, 0)
        NodeChildrenGenerator.generate(self.root)

    def setThreads(self, n):
        self.numThreads = n

    def doRollout(self):
        if self.root and self.root.terminal==0:
            RolloutManager.rollout(self.root, self.root.rollouts)

    def makeMove(self):
        if not self.root.children:
            self.doRollout()
            NodeChildrenGenerator.generate(self.root)
        if not self.root.children:
            move_list = self.gateway.jvm.java.util.ArrayList()
            for _ in range(3):
                move_list.add(self.gateway.jvm.java.util.ArrayList())
            return move_list
        highest_ucb1score_node = max(self.root.children, key=lambda c: c.ucb1Score)
        self.root = highest_ucb1score_node
        move_list = self.gateway.jvm.java.util.ArrayList()
        for (row, column) in (highest_ucb1score_node.queenCurrent, highest_ucb1score_node.queenNew, highest_ucb1score_node.arrow):
            row_mapped = 10 - row
            column_mapped = column + 1
            mapped_coords = self.gateway.jvm.java.util.ArrayList()
            mapped_coords.add(int(row_mapped))
            mapped_coords.add(int(column_mapped))
            move_list.add(mapped_coords)
        return move_list

    def isOpponentMoveValid(self, queen_curr, queen_new, arrow_shot):
        return OpponentValidator.validate(self.root, queen_curr, queen_new, arrow_shot)

# Creating Py4J gateway for Java to connect 
if __name__ == "__main__":
    gateway_entry_point = MCTSBridge()
    server = ClientServer(
        java_parameters   = JavaParameters(),
        python_parameters = PythonParameters(),
        python_server_entry_point = gateway_entry_point
    )
    gateway_entry_point.gateway = server
    print("Python bridge used")