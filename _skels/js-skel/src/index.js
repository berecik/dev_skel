/**
 * JavaScript Skeleton Project
 * Entry point
 */

const PORT = process.env.PORT || 3000;

function greet(name = 'World') {
  return `Hello, ${name}!`;
}

function main() {
  console.log(greet());
  console.log(`Server would run on port ${PORT}`);
}

export { greet };

main();
