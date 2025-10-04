# Use Debian-based Node 20 to fix both crypto + version issues
FROM node:20-bookworm
WORKDIR /app

# Copy package.json and install dependencies
COPY package*.json ./
RUN npm install

# Copy all frontend files
COPY . .

# Expose Vite’s default dev server port
EXPOSE 5173

# Start in development mode
CMD ["npm", "run", "dev", "--", "--host"]
