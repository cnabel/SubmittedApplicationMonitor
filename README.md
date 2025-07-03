# SubmittedApplicationMonitor

A Red-Discord Bot cog that monitors membership applications and notifies specified roles when users apply to join servers with membership screening enabled.

## Installation

1. Add this repository to your Red-bot:
   ```
   [p]repo add submittedapplicationmonitor https://github.com/cnabel/SubmittedApplicationMonitor
   ```

2. Install the cog:
   ```
   [p]cog install submittedapplicationmonitor applicationmonitor
   ```

3. Load the cog:
   ```
   [p]load applicationmonitor
   ```

## Features

- **Real-time monitoring** of membership applications
- **Role notifications** when new applications are received
- **Approval tracking** when members complete screening
- **Rich embed notifications** with user details and timestamps
- **Per-guild configuration** for different servers

## Commands

All commands require `Manage Server` permission or administrator privileges.

- `[p]appmonitor channel <channel>` - Set the notification channel
- `[p]appmonitor role <role>` - Set the role to notify
- `[p]appmonitor toggle` - Enable/disable monitoring
- `[p]appmonitor settings` - View current configuration

## Setup Guide

1. **Set notification channel:**
   ```
   [p]appmonitor channel #applications
   ```

2. **Set notification role:**
   ```
   [p]appmonitor role @Moderators
   ```

3. **Enable monitoring:**
   ```
   [p]appmonitor toggle
   ```

4. **Verify settings:**
   ```
   [p]appmonitor settings
   ```

## Requirements

- Your Discord server must have **Membership Screening** enabled (Rules Channel configured)
- The bot needs permissions to:
  - Send messages in the notification channel
  - Mention the notification role
  - View server members

## How It Works

The cog monitors two events:
1. **New Applications**: When users join with pending membership screening
2. **Approved Applications**: When users complete the screening process

Both events trigger notifications to the configured channel with the specified role mention.

## Support

If you encounter any issues:
1. Check that membership screening is enabled on your server
2. Verify the bot has proper permissions
3. Ensure the notification channel and role are properly configured
4. Open an issue on this repository if problems persist

## License

This project is licensed under the MIT License.
