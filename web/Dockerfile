# Next.js dashboard (production). Build arg NEXT_PUBLIC_API_URL must be the
# browser-reachable backend base, e.g. http://localhost:8000 in compose.
FROM node:20-alpine AS build
WORKDIR /web
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:20-alpine AS run
WORKDIR /web
ENV NODE_ENV=production
COPY --from=build /web/package.json /web/package-lock.json ./
COPY --from=build /web/.next ./.next
COPY --from=build /web/public ./public
COPY --from=build /web/node_modules ./node_modules
EXPOSE 3000
CMD ["npm", "run", "start", "--", "-p", "3000", "-H", "0.0.0.0"]
