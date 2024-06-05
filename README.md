# Discord Poll Bot

This Discord bot allows users to create and manage polls within Discord servers. It supports both single-choice and multiple-choice polls, with the ability to set an end date for each poll.

## Features

- **Single-choice Polls**: Users can create polls with a single-choice selection from a list of options.
- **Multiple-choice Polls**: Users can create polls with multiple-choice selections from a list of options.
- **Customizable End Date**: Poll creators can set an end date for each poll, after which voting is no longer allowed.
- **Real-time Results**: Participants can view real-time poll results, which are updated automatically.
- **Interactive Interface**: The bot provides an interactive interface for creating, voting in, and viewing poll results.

## Commands

- **!single_poll "question" "end_date" "option1" "option2" ...**: Create a single-choice poll with the specified question, end date, and options.
- **!multi_poll "question" "end_date" "option1" "option2" ...**: Create a multiple-choice poll with the specified question, end date, and options.
- **!poll_help**: Display instructions on how to use the bot and create polls.

## Installation

1. Clone the repository: `git clone <repository-url>`
2. Install the required dependencies: `pip install -r requirements.txt`
3. Create a `.env` file in the root directory and add your Discord bot token: `DISCORD_TOKEN=<your-bot-token>`
4. Run the bot: `python VoteBot.py`

## Usage

1. Invite the bot to your Discord server using the invite link generated from your Discord Developer Portal.
2. Use the `!poll_help` command to get instructions on how to create polls.
3. Create a poll using either `!single_poll` or `!multi_poll` commands, providing the question, end date, and options.
4. Participants can vote in the poll by clicking on the provided buttons.
5. View real-time poll results by clicking on the "Show results" button.
