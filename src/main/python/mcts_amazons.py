import math, random, threading
from py4j.clientserver import ClientServer, JavaParameters, PythonParameters

class Action:
    def __init__(self, qc, qn, ar, id_):
        self.qc, self.qn, self.ar, self.id = qc, qn, ar, id_
    def getQueenPositionCurrent(self): return self.qc
    def getQueenPositionNew(self):     return self.qn
    def getArrowPosition(self):        return self.ar
    def getId(self):                   return self.id

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

class NodeChildrenGenerator:
    @staticmethod
    def generate(node):
        acts = ActionFactory(node.state, node.playerType).get_actions()
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

class OpponentValidator:
    @staticmethod
    def validate(node, qc, qn, ar):
        acts = ActionFactory(node.state, node.playerType).get_actions()
        for a in acts:
            if (a.getQueenPositionCurrent()==qc and
                a.getQueenPositionNew()==qn and
                a.getArrowPosition()==ar):
                cid = a.getId()
                if cid in node.currentChildren:
                    node.__dict__.update(node.currentChildren[cid].__dict__)
                else:
                    st = [r[:] for r in node.state]
                    st[qc[0]][qc[1]] = 0
                    st[qn[0]][qn[1]] = node.playerType
                    st[ar[0]][ar[1]] = 7
                    child = Node(st, 2 if node.playerType==1 else 1, qc,qn,ar,cid)
                    node.__dict__.update(child.__dict__)
                return True
        return False

class MCTSBridge:
    def __init__(self):
        self.root = None
        self.numThreads = 1

    def setCurrentNode(self, boardState, playerId):
        self.root = Node(boardState, playerId, None, None, None, 0)

    def setThreads(self, n):
        self.numThreads = n

    def doRollout(self):
        if self.root and self.root.terminal==0:
            RolloutManager.rollout(self.root, self.root.rollouts)

    def makeMove(self):
        best = max(self.root.children, key=lambda c: c.ucb1Score)
        self.root = best
        return [best.queenCurrent, best.queenNew, best.arrow]

    def isOpponentMoveValid(self, qc, qn, ar):
        return OpponentValidator.validate(self.root, qc, qn, ar)

if __name__ == "__main__":
    entry = MCTSBridge()
    server = ClientServer(
        java_parameters   = JavaParameters(),
        python_parameters = PythonParameters(),
        python_server_entry_point = entry
    )
    print("Python bridge used")