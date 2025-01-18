# Discord Bot for Minecraft Champs

Welcome to the **Minecraft Champs Discord Bot** repository! This bot is a custom-built solution designed to enhance your parody of the Lunar.gg server. It offers an automated ELO calculation system, leaderboards, match history, match result statistics, and anti-abuse features to maintain the integrity of your competition.

## Features

### 1. **ELO Rating System**
- Implements the [ELO rating system](https://en.wikipedia.org/wiki/Elo_rating_system) to calculate player ratings based on match outcomes.
- Ensures fair competition and dynamic ranking adjustments after every duel.

### 2. **Leaderboards**
- Real-time leaderboards displaying the top players and their ELO rankings.
- Provides insights into player performance and standings.

### 3. **Match History**
- Keeps track of all past duels, including players, outcomes, and ELO changes.
- Allows players to review their performance and match records.

### 4. **Match Result Statistics**
- Records match outcomes, including who won and the resulting ELO changes.
- Enables players to track their progress and competition results.

### 5. **Anti-Boosting Measures**
- **Duel Limits**: Restricts the number of duels between the same players within a given timeframe to prevent ELO boosting.
- **Duel Bans**: Automatically bans players from dueling if suspicious patterns indicative of ELO boosting are detected.

## Installation

1. **Clone the Repository**
   ```bash
   git clone https://github.com/Mekvil/Champs
   cd Champs
   ```

2. **Install Dependencies**
   Make sure you have Python installed. Then, run:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure the Bot**
   - Set bot token in `.env` file, setup channels in `main.py`.

4. **Run the Bot**
   ```bash
   python bot.py
   ```

## Commands

| Command               | Description                                            |
|-----------------------|--------------------------------------------------------|
| `/match`              | Record a match result.                                 |
| `/rating`             | Check your or another player's rating.                |
| `/register`           | Register a player in the rating system.               |
| `/reset_limits`       | Reset all match limits.                                |
| `/setup_lfg`          | Setup the Looking For Fight button.                   |
| `/setup_rules`        | Setup the rules acceptance button.                    |

## Contributing

Feel free to contribute to this project by submitting issues or pull requests. Ensure that your contributions align with the bot's purpose and functionality.

## Credits

This bot was created by **Mekvil** with a focus on providing a fun and fair competitive experience for Minecraft Champs. Special thanks to contributors and testers who helped refine this project.

## License

This project is licensed under the [MIT License](LICENSE).

---

Enjoy using the Minecraft Champs Discord Bot!
