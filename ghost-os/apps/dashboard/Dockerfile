FROM node:20-alpine
RUN apk add --no-cache libc6-compat openssl
RUN npm install -g pnpm

WORKDIR /app

# Disable telemetry
ENV NEXT_TELEMETRY_DISABLED 1

# Copy the entire monorepo
# This is made efficient by the .dockerignore file
COPY . .

# Install dependencies for the whole workspace
RUN pnpm install

# Generate Prisma client using the project's prisma version (v5)
# Using pnpm recursive exec or filter to ensure we use the local prisma binary
RUN pnpm --filter @ghost-os/database exec prisma generate

# Build the dashboard app
RUN pnpm --filter dashboard build

# Expose port
EXPOSE 3000

# Start the app
WORKDIR /app/apps/dashboard
CMD ["pnpm", "start"]
