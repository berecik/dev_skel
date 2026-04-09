/**
 * JavaScript Skeleton Project
 * Entry point
 */

import { config } from './config.js';

function greet(name = 'World') {
  return `Hello, ${name}!`;
}

function main() {
  console.log(greet());
  console.log(
    `Server would bind to ${config.service.host}:${config.service.port}`
  );
  console.log(`Database URL: ${config.databaseUrl}`);
  console.log(`JWT issuer: ${config.jwt.issuer}`);
}

export { greet };

main();
