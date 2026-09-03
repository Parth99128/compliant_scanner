FROM node:20-alpine AS build
WORKDIR /web
COPY package.json ./
RUN npm install
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /web/dist /usr/share/nginx/html
EXPOSE 80
