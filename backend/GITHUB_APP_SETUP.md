# GitHub App Authentication Setup Guide

This guide explains how to set up GitHub App authentication for the Yudai backend.

## 1. Create a GitHub App

1. Go to [GitHub Developer Settings](https://github.com/settings/apps)
2. Click "New GitHub App"
3. Fill in the basic information:
   - **App name**: `yudai-app` (or your preferred name)
   - **Homepage URL**: `https://yudai.app`
   - **Callback URL**: `https://yudai.app/auth/callback`
   - **Webhook**: Disable for now
   - **Permissions**: 
     - Repository access: `Read and write`
     - Issues: `Read and write`
     - Pull requests: `Read and write`
     - Contents: `Read and write`
     - Metadata: `Read-only`

## 2. Generate Private Key

1. After creating the app, go to "Private keys"
2. Click "Generate private key"
3. Download the `.pem` file
4. Place it in the `backend/` directory as `private-key.pem`

## 3. Install the GitHub App

1. Go to your GitHub App's page
2. Click "Install App"
3. Choose the repositories you want to install it on
4. Note the Installation ID from the URL

## 4. Environment Variables

Add these environment variables to your `.env` file:

```bash
# GitHub App Configuration
GITHUB_APP_ID=your_app_id_from_github_app_page
GITHUB_APP_CLIENT_ID=your_client_id_from_github_app_page
GITHUB_APP_CLIENT_SECRET=your_client_secret_from_github_app_page
GITHUB_APP_INSTALLATION_ID=your_installation_id
GITHUB_APP_PRIVATE_KEY_PATH=private-key.pem
GITHUB_REDIRECT_URI=https://yudai.app/auth/callback

# Frontend URL for redirects
FRONTEND_URL=http://localhost:3000
```

## 5. Install Dependencies

```bash
pip install PyJWT==2.8.0 cryptography==41.0.7
```

## 6. Test the Setup

1. Start your backend server
2. Visit `/auth/config` to verify configuration
3. Visit `/auth/login` to test the OAuth flow

## 7. Integration with WebSocket Sessions

The authentication is now properly integrated with the WebSocket sessions in `chat_api.py`. The WebSocket endpoint uses the same authentication mechanism:

```python
@router.websocket("/sessions/{session_id}/ws")
async def websocket_session_endpoint(
    websocket: WebSocket,
    session_id: str,
    token: Optional[str] = None,
    db: Session = Depends(get_db),
):
    # Uses the same get_current_user function
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    user = await get_current_user(credentials, db)
```

## Troubleshooting

### Common Issues

1. **JWT Generation Fails**: Check that the private key file exists and is readable
2. **Installation Token Fails**: Verify the Installation ID is correct
3. **OAuth Callback Fails**: Ensure the callback URL matches exactly
4. **Token Validation Fails**: Check that tokens are being stored correctly in the database

### Debug Steps

1. Check the logs for JWT generation errors
2. Verify all environment variables are set
3. Test the OAuth flow manually
4. Check database connectivity and token storage

## Security Notes

- Keep the private key secure and never commit it to version control
- Use environment variables for all sensitive configuration
- Regularly rotate the private key
- Monitor token usage and expiration 