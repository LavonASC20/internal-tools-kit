FROM node:20-alpine
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
EXPOSE 5173
# API_TARGET points the /api proxy at the backend, e.g. http://backend:8000
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
