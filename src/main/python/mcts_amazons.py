# pip install py4j and run this file first and then run COSC322GamePlayer.java and run another instance of COSC322GamePlayer.java that have both joined the same game room
import math, random, threading
from py4j.clientserver import ClientServer, JavaParameters, PythonParameters

# queen current pos, queen new pos, shot arrow pos
class Action:
    def __init__(self, qc, qn, ar, id_):
        self.qc, self.qn, self.ar, self.id = qc, qn, ar, id_
    def getQueenPositionCurrent(self): return self.qc
    def getQueenPositionNew(self):     return self.qn
    def getArrowPosition(self):        return self.ar
    def getId(self):                   return self.id

# Getting possible actions
class ActionFactory:
    DIRS = [(1,0),(1,1),(1,-1),(-1,0),(-1,1),(-1,-1),(0,-1),(0,1)]
    def __init__(self, state, player):
        self.state = [row[:] for row in state]
        self.player = player
        self._next_id = 0

    def get_actions(self):
        acts = []
        for x in range(10):
            for y in range(10):
                if self.state[x][y] == self.player:
                    acts.extend(self._queen_moves(x,y))
        return acts

    def _queen_moves(self, x, y):
        res = []
        for dx,dy in ActionFactory.DIRS:
            step = 1
            while True:
                nx,ny = x+dx*step, y+dy*step
                if not (0 <= nx < 10 and 0 <= ny < 10 and self.state[nx][ny]==0):
                    break
                res += self._arrow_shots([x,y],[nx,ny])
                step += 1
        return res

    def _arrow_shots(self, qc, qn):
        sc = [row[:] for row in self.state]
        sc[qc[0]][qc[1]] = 0
        sc[qn[0]][qn[1]] = self.player
        shots = []
        for dx,dy in ActionFactory.DIRS:
            step = 1
            while True:
                ax,ay = qn[0]+dx*step, qn[1]+dy*step
                if not (0 <= ax < 10 and 0 <= ay < 10 and sc[ax][ay]==0):
                    break
                self._next_id += 1
                shots.append(Action(qc,qn,[ax,ay],self._next_id))
                step += 1
        return shots

# State in MCTS
class Node:
    def __init__(self, st, playerType, qc, qn, ar, id_):
        self.state       = [row[:] for row in st]
        self.playerType  = playerType
        self.queenCurrent= qc
        self.queenNew    = qn
        self.arrow       = ar
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
        c = math.sqrt(2)
        self.ucb1Score = self.avg_win() + c*math.sqrt(math.log(parentRollouts)/self.rollouts) - self.punishment

# Prunes MCTS tree
class NodeChildrenGenerator:
    @staticmethod
    def generate(node):
        node.children.clear()
        acts = ActionFactory(node.state, node.playerType).get_actions()
        valid_ids = {a.getId() for a in acts}
        node.currentChildren = {
            id_: child
            for id_, child in node.currentChildren.items()
            if id_ in valid_ids
        }
        if node.terminal == -1:
            if not acts:
                node.terminal = 2 if node.playerType==1 else 1
            else:
                node.terminal = 0
        if node.terminal!=0:
            return
        for a in acts:
            if a.getId() in node.currentChildren:
                child = node.currentChildren[a.getId()]
            else:
                st = [r[:] for r in node.state]
                oc, on, ar = a.getQueenPositionCurrent(), a.getQueenPositionNew(), a.getArrowPosition()
                st[oc[0]][oc[1]] = 0
                st[on[0]][on[1]] = node.playerType
                st[ar[0]][ar[1]] = 7
                child = Node(st, 2 if node.playerType==1 else 1, oc, on, ar, a.getId())
                node.currentChildren[a.getId()] = child
            node.children.append(child)

# Picks a node to rollout
class RolloutManager:
    @staticmethod
    def rollout(node, parentRollouts):
        NodeChildrenGenerator.generate(node)
        if node.terminal!=0:
            return node.terminal
        node.rollouts += 1
        acts = ActionFactory(node.state, node.playerType).get_actions()
        choice = random.choice(acts)
        cid = choice.getId()
        if cid in node.currentChildren:
            nxt = node.currentChildren[cid]
        else:
            st = [r[:] for r in node.state]
            oc,on,ar = choice.getQueenPositionCurrent(), choice.getQueenPositionNew(), choice.getArrowPosition()
            st[oc[0]][oc[1]] = 0
            st[on[0]][on[1]] = node.playerType
            st[ar[0]][ar[1]] = 7
            nxt = Node(st, 2 if node.playerType==1 else 1, oc,on,ar, cid)
            node.currentChildren[cid] = nxt
        winner = RolloutManager.rollout(nxt, node.rollouts)
        if winner == node.playerType:
            node.totalWins += 1
        else:
            node.punishment += 0.3
        node.update_ucb1(parentRollouts)
        return winner

# Factor in opponent move
class OpponentValidator:
    @staticmethod
    def validate(node, qc, qn, ar):
        def transform(pos):
            return [10 - pos[0], pos[1] - 1]

        qc_t = transform(qc)
        qn_t = transform(qn)
        ar_t = transform(ar)
        acts = ActionFactory(node.state, node.playerType).get_actions()
        for a in acts:
            if (a.getQueenPositionCurrent() == qc_t
                and a.getQueenPositionNew()     == qn_t
                and a.getArrowPosition()        == ar_t):
                if a.getId() in node.currentChildren:
                    node.__dict__.update(node.currentChildren[a.getId()].__dict__)
                else:
                    st = [r[:] for r in node.state]
                    st[qc_t[0]][qc_t[1]] = 0
                    st[qn_t[0]][qn_t[1]] = node.playerType
                    st[ar_t[0]][ar_t[1]] = 7
                    child = Node(st, 2 if node.playerType==1 else 1, qc_t, qn_t, ar_t, a.getId())
                    node.__dict__.update(child.__dict__)
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
        py_state = []
        for java_row in boardState:
            py_state.append([int(cell) for cell in java_row])
        self.root = Node(py_state, playerId, None, None, None, 0)
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
            jouter = self.gateway.jvm.java.util.ArrayList()
            for _ in range(3):
                jouter.add(self.gateway.jvm.java.util.ArrayList())
            return jouter
        best = max(self.root.children, key=lambda c: c.ucb1Score)
        self.root = best
        jouter = self.gateway.jvm.java.util.ArrayList()
        for (r, c) in (best.queenCurrent, best.queenNew, best.arrow):
            sf_r = 10 - r
            sf_c = c + 1
            jinner = self.gateway.jvm.java.util.ArrayList()
            jinner.add(int(sf_r))
            jinner.add(int(sf_c))
            jouter.add(jinner)
        return jouter

    def isOpponentMoveValid(self, qc, qn, ar):
        return OpponentValidator.validate(self.root, qc, qn, ar)

# Creating Py4J gateway for Java to connect 
if __name__ == "__main__":
    entry = MCTSBridge()
    server = ClientServer(
        java_parameters   = JavaParameters(),
        python_parameters = PythonParameters(),
        python_server_entry_point = entry
    )
    entry.gateway = server
    print("Python bridge used")