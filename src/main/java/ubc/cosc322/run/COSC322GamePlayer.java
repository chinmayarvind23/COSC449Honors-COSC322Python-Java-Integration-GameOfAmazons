package ubc.cosc322.run;

import java.util.*;

import py4j.ClientServer;
import sfs2x.client.entities.Room;
import ubc.cosc322.mcts.MCTS_Manager;
import ygraph.ai.smartfox.games.BaseGameGUI;
import ygraph.ai.smartfox.games.GameClient;
import ygraph.ai.smartfox.games.GameMessage;
import ygraph.ai.smartfox.games.GamePlayer;
import ygraph.ai.smartfox.games.amazons.AmazonsGameMessage;

public class COSC322GamePlayer extends GamePlayer {
	// Gets methods from Python code
    private interface PythonMcts {
        void setCurrentNode(int[][] boardState, int playerId);
        void setThreads(int n);
        void doRollout();
        List<List<Integer>> makeMove();
        boolean isOpponentMoveValid(List<Integer> qc,
                                    List<Integer> qn,
                                    List<Integer> ar);
    }

	private GameClient gameClient = null;
	private BaseGameGUI gamegui = null;

	private ClientServer pyServer;
    private PythonMcts  pythonMcts;

	private String userName = null;
	private String passwd = null;

	private int myQueen = -1;

	private int[][] board = null;




	public static void main(String[] args) {
		COSC322GamePlayer player;
		String userName, passwd;
		if(args.length == 0)
		{

			Random random = new Random();
			userName = "MCTS_Team_13#" + random.nextInt(1000);
			passwd = "password";
			player = new COSC322GamePlayer(userName, passwd);


		}
		else player = new COSC322GamePlayer(args[0], args[1]);

		if (player.getGameGUI() == null) {
			player.Go();
		} else {
			BaseGameGUI.sys_setup();
			java.awt.EventQueue.invokeLater(new Runnable() {
				public void run() {
					player.Go();
				}
			});
		}
	}


	public COSC322GamePlayer(String userName, String passwd) {
		this.userName = userName;
		this.passwd = passwd;
		this.board = new int[10][10];

		// To make a GUI-based player, create an instance of BaseGameGUI
		// and implement the method getGameGUI() accordingly
		this.gamegui = new BaseGameGUI(this);
	}

	// Login to SFS, spin up connection to Py4J gateway
	@Override
	public void connect() {
		gameClient = new GameClient(userName, passwd, this);
		pyServer = new ClientServer((Object) null);
		pythonMcts = (PythonMcts) pyServer
			.getPythonServerEntryPoint(new Class[]{ PythonMcts.class });
		System.out.println("Connected to Python MCTS bridge? " + (pythonMcts != null));
	}

	@Override
	public GameClient getGameClient() {
		return this.gameClient;
	}

	@Override
	public BaseGameGUI getGameGUI() {
		return this.gamegui;
	}

	@SuppressWarnings("unchecked")
	@Override
	public boolean handleGameMessage(String messageType, Map<String, Object> msgDetails) {
		System.out.println("Message Type: "+messageType);

		switch (messageType) {
			case GameMessage.GAME_STATE_BOARD:
				if (gamegui != null) {
					ArrayList<Integer> board = (ArrayList<Integer>) msgDetails.get(AmazonsGameMessage.GAME_STATE);
					this.board = initGameBoard();
					this.gamegui.setGameState(board);


				}
				break;

			    case GameMessage.GAME_ACTION_START:
					setMyQueen((String) msgDetails.get(AmazonsGameMessage.PLAYER_BLACK));
					// Calling python code
					pythonMcts.setCurrentNode(board, myQueen);
					pythonMcts.setThreads(4);

					if (myQueen == 2) {
						RolloutThread thinker = new RolloutThread();
						thinker.start();
						try {
							Thread.sleep(15000);
						} catch (InterruptedException e) {
							Thread.currentThread().interrupt();
						}
						thinker.stopThread();
						makeDecisionAndSend();
					}
					break;

				case GameMessage.GAME_ACTION_MOVE:
					if (gamegui != null) {
						gamegui.updateGameState(msgDetails);
					}

					List<Integer> qc = (List<Integer>) msgDetails.get(AmazonsGameMessage.QUEEN_POS_CURR);
					List<Integer> qn = (List<Integer>) msgDetails.get(AmazonsGameMessage.QUEEN_POS_NEXT);
					List<Integer> ar = (List<Integer>) msgDetails.get(AmazonsGameMessage.ARROW_POS);
					if (!pythonMcts.isOpponentMoveValid(qc, qn, ar)) {
						System.err.println("Invalid opponent move");
					} else {
						RolloutThread thinker2 = new RolloutThread();
						thinker2.start();
						try {
							Thread.sleep(15000);
						} catch (InterruptedException e) {
							Thread.currentThread().interrupt();
						}
						thinker2.stopThread();
						makeDecisionAndSend();
					}
					break;
			

			case AmazonsGameMessage.GAME_STATE_PLAYER_LOST:
				System.out.println("Our AI has won!");
				gameClient.leaveCurrentRoom();
				gameClient.logout();
		}
		return true;
	}

	private void setMyQueen(String playingBlackQueens) {
		if (this.userName.equals(playingBlackQueens)) {
			this.myQueen = 2;
		} else {
			this.myQueen = 1;
		}
	}

	private int[][] initGameBoard() {

		return new int[][]{
				{0, 0, 0, 2, 0, 0, 2, 0, 0, 0},
				{0, 0, 0, 0, 0, 0, 0, 0, 0, 0},
				{0, 0, 0, 0, 0, 0, 0, 0, 0, 0},
				{2, 0, 0, 0, 0, 0, 0, 0, 0, 2},
				{0, 0, 0, 0, 0, 0, 0, 0, 0, 0},
				{0, 0, 0, 0, 0, 0, 0, 0, 0, 0},
				{1, 0, 0, 0, 0, 0, 0, 0, 0, 1},
				{0, 0, 0, 0, 0, 0, 0, 0, 0, 0},
				{0, 0, 0, 0, 0, 0, 0, 0, 0, 0},
				{0, 0, 0, 1, 0, 0, 1, 0, 0, 0},
		};
	}


	@Override
	public void onLogin() {
		System.out.println("Congratualations!!! "
				+ "I am called because the server indicated that the login is successfully");
		System.out.println("The next step is to find a room and join it: "
				+ "the gameClient instance created in my constructor knows how!");
		this.userName = gameClient.getUserName();
		List<Room> rooms = this.gameClient.getRoomList();
		for (Room room : rooms) {
			System.out.println(room);
		}
		if (gamegui != null) {
			gamegui.setRoomInformation(gameClient.getRoomList());
		}

		try (Scanner scanner = new Scanner(System.in)) {
			System.out.print("Enter a room number");
			int roomIdx = scanner.nextInt();
			this.gameClient.joinRoom(rooms.get(roomIdx).getName());
		}




	}

	@Override
	public String userName() {
		return userName;
	}



	public void performRolloutsOnCurrentNodeFor30Seconds() throws InterruptedException {
		RolloutThread rolloutThread = new RolloutThread();
		rolloutThread.start();
		Thread.sleep(15000);
		rolloutThread.stopThread();
		System.out.println("AI has finished thinking");
	}
	
	// makes decision from python code
	private void makeDecisionAndSend() {
	List<List<Integer>> mv = pythonMcts.makeMove();
	if (mv == null || mv.size() < 3 || mv.get(0).size() < 2 || mv.get(1).size() < 2 || mv.get(2).size() < 2) {
        System.out.println("No legal moves left — ending game.");
        gameClient.leaveCurrentRoom();
        gameClient.logout();
        pyServer.shutdown();
        return;
    }
	// queen current pos, queen new pos, shot arrow pos
	ArrayList<Integer> qcArr = new ArrayList<>(mv.get(0));
	ArrayList<Integer> qnArr = new ArrayList<>(mv.get(1));
	ArrayList<Integer> arArr = new ArrayList<>(mv.get(2));

	gamegui.updateGameState(qcArr, qnArr, arArr);
	gameClient.sendMoveMessage(qcArr, qnArr, arArr);
	}

	public void printArray()
	{
		int[][] state = MCTS_Manager.getNode().getState();
		for (int i = 0; i < 10; i++) {
			for (int j = 0; j < 10; j++) {
				System.out.print(state[i][j]+" ");
			}
			System.out.println();
		}
	}

	class RolloutThread extends Thread {
		private volatile boolean running = true;
		public void run() {
			while (running) {
				pythonMcts.doRollout();
			}
		}
		public void stopThread() {
			running = false;
		}
	}	
}
