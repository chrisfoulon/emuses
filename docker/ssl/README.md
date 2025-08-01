# SSL Certificate Configuration

This directory should contain SSL certificates for HTTPS configuration in production.

## Development Setup

For development, you can generate self-signed certificates:

```bash
# Generate private key
openssl genrsa -out server.key 2048

# Generate certificate signing request
openssl req -new -key server.key -out server.csr

# Generate self-signed certificate (valid for 365 days)
openssl x509 -req -days 365 -in server.csr -signkey server.key -out server.crt

# Remove CSR file (no longer needed)
rm server.csr
```

## Production Setup

For production, obtain certificates from a trusted Certificate Authority (CA) or use Let's Encrypt:

### Let's Encrypt with Certbot

```bash
# Install certbot
sudo apt-get install certbot

# Obtain certificate
sudo certbot certonly --standalone -d yourdomain.com

# Copy certificates to this directory
sudo cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem server.crt
sudo cp /etc/letsencrypt/live/yourdomain.com/privkey.pem server.key

# Set proper permissions
sudo chown emuses:emuses server.crt server.key
chmod 644 server.crt
chmod 600 server.key
```

### Manual Certificate Installation

1. Obtain certificates from your CA
2. Copy the certificate to `server.crt`
3. Copy the private key to `server.key`
4. Ensure proper file permissions:
   - `server.crt`: 644 (readable by all)
   - `server.key`: 600 (readable only by owner)

## File Structure

```
docker/ssl/
├── README.md          # This file
├── server.crt         # SSL certificate (public)
└── server.key         # SSL private key (secret)
```

## Security Notes

- Never commit `server.key` to version control
- Use strong encryption for private keys in production
- Regularly rotate certificates (recommended: every 90 days)
- Monitor certificate expiration dates