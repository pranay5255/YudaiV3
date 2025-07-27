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
| A | @ | YOUR_VULTR_IP | 600 | Root domain |
| A | www | YOUR_VULTR_IP | 600 | WWW subdomain |
| CNAME | api | yudai.app | 600 | API subdomain |
| A | * | YOUR_VULTR_IP | 600 | Wildcard subdomains |

### Step 4: Save and Verify
1. Click "Save" or "Save All"
2. Wait for confirmation
3. Test with: `nslookup yudai.app`

## 🔧 Detailed Instructions

### Adding A Records
1. Click "Add" or "+" button
2. Select "A" from record type dropdown
3. For root domain:
   - **Name**: `@` (or leave blank)
   - **Value**: `YOUR_VULTR_SERVER_IP`
   - **TTL**: `600`
4. For www subdomain:
   - **Name**: `www`
   - **Value**: `YOUR_VULTR_SERVER_IP`
   - **TTL**: `600`

### Adding CNAME Records
1. Click "Add" or "+" button
2. Select "CNAME" from record type dropdown
3. **Name**: `api`
4. **Value**: `yudai.app`
5. **TTL**: `600`

### Adding Wildcard Record
1. Click "Add" or "+" button
2. Select "A" from record type dropdown
3. **Name**: `*`
4. **Value**: `YOUR_VULTR_SERVER_IP`
5. **TTL**: `600`

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

# Test wildcard subdomain
nslookup test.yudai.app
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