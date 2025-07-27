# GoDaddy DNS Configuration Quick Reference

## 🎯 Quick Setup Checklist

### Step 1: Access GoDaddy DNS
1. Go to [godaddy.com](https://godaddy.com)
2. Sign in to your account
3. Click "Domains" → "My Domains"
4. Click on `yudai.app`
5. Click "DNS" or "Manage DNS"

### Step 2: Remove Default Records
- Delete any existing A records pointing to GoDaddy's parking page
- Look for records with values like `50.63.202.1` or similar GoDaddy IPs

### Step 3: Add Required DNS Records

| Type | Name | Value | TTL | Purpose |
|------|------|-------|-----|---------|
| A | @ | YOUR_VULTR_IP | 1 Hour | Root domain |
| A | api | YOUR_VULTR_IP | 1 Hour | API subdomain |
| A | dev | YOUR_VULTR_IP | 1 Hour | Development subdomain |
| A | www | YOUR_VULTR_IP | 1 Hour | WWW subdomain |

### Step 4: Save and Verify
1. Click "Save" or "Save All"
2. Wait for confirmation
3. Test with: `nslookup yudai.app`

## 🔧 Detailed Instructions

### Updating Root Domain A Record
1. **Find the existing `@` A record** (usually pointing to "WebsiteBuilder Site")
2. **Click "Edit"** on the `@` A record
3. **Update the "Data" field** with your Vultr IP address
4. **Save the changes**

### Adding API Subdomain A Record
1. Click "Add" or "+" button
2. Select "A" from record type dropdown
3. **Name**: `api`
4. **Value**: `YOUR_VULTR_IP` (e.g., 143.110.123.45)
5. **TTL**: `1 Hour`
6. **Click "Save"**

### Adding Development Subdomain A Record
1. Click "Add" or "+" button
2. Select "A" from record type dropdown
3. **Name**: `dev`
4. **Value**: `YOUR_VULTR_IP` (e.g., 143.110.123.45)
5. **TTL**: `1 Hour`
6. **Click "Save"**

### Adding WWW Subdomain A Record
1. Click "Add" or "+" button
2. Select "A" from record type dropdown
3. **Name**: `www`
4. **Value**: `YOUR_VULTR_IP` (e.g., 143.110.123.45)
5. **TTL**: `1 Hour`
6. **Click "Save"**

## ⚠️ Common Mistakes

### ❌ Don't Do This:
- Change nameservers to custom ones
- Use CNAME for root domain (@)
- Set TTL to 0 or very low values
- Add duplicate records
- Use IP addresses from other providers

### ✅ Do This:
- Keep GoDaddy's default nameservers
- Use A records for root domain
- Set TTL to 600 or higher
- Use your Vultr server IP address
- Test DNS resolution after changes

## 🧪 Testing DNS Configuration

### Command Line Testing
```bash
# Test root domain
nslookup yudai.app

# Test www subdomain
nslookup www.yudai.app

# Test API subdomain
nslookup api.yudai.app

# Test development subdomain
nslookup dev.yudai.app
```

### Online Testing Tools
- [whatsmydns.net](https://www.whatsmydns.net/)
- [dnschecker.org](https://dnschecker.org/)
- [mxtoolbox.com](https://mxtoolbox.com/)

## 📞 GoDaddy Support

If you encounter issues:
1. **Live Chat**: Available 24/7 on GoDaddy website
2. **Phone Support**: 1-480-505-8877
3. **Help Center**: [help.godaddy.com](https://help.godaddy.com)

## 🔄 DNS Propagation Timeline

| Location | Time |
|----------|------|
| Local/ISP | 5-30 minutes |
| Regional | 1-4 hours |
| Global | 24-48 hours |
| Full propagation | Up to 72 hours |

**Note**: You can proceed with SSL certificate setup once local DNS resolution works.