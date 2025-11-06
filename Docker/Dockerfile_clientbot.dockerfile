FROM node:18-alpine
WORKDIR /app
COPY ./req-rep/js-bot/package.json ./
RUN npm install --silent
COPY ./req-rep/js-bot ./
CMD ["node","bot.js"]
