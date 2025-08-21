/**
 * Minimal esbuild configuration to bundle the React app for CI builds.
 * This is a lightweight replacement when Vite or CRA are unavailable in the environment.
 * Uses CommonJS so it runs under Node without ESM.
 */
const esbuild = require('esbuild');

const isProd = process.env.NODE_ENV === 'production';

esbuild.build({
  entryPoints: ['src/index.js'],
  bundle: true,
  minify: isProd,
  sourcemap: !isProd,
  outdir: 'dist',
  define: {
    'process.env.NODE_ENV': JSON.stringify(process.env.NODE_ENV || 'production'),
  },
  loader: {
    '.js': 'jsx'
  }
}).catch((err) => {
  console.error(err);
  process.exit(1);
});
