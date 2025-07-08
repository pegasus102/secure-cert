from pyngrok import ngrok, conf

conf.get_default().auth_token = "2zYQPdPNYFjvRUujAN2Z6w5Vu31_3B9LxkdeSwLyRMZVEYxU1"

# Expose your Flask server (port 5000)
tunnel = ngrok.connect(5000)
public_url = tunnel.public_url

print(" * Ngrok Tunnel URL:", public_url)

print(f" * Admin page  → {public_url}/admin")
print(f" * Verify page → {public_url}/verify")

input("Press ENTER to stop tunnel...\n")
ngrok.disconnect(public_url)
