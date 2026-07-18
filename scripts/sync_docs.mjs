import { cp, mkdir, rm } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";

const scriptDirectory = path.dirname(fileURLToPath(import.meta.url));
const repositoryRoot = path.resolve(scriptDirectory, "..");
const source = path.join(repositoryRoot, "docs");
const destination = path.join(repositoryRoot, "apps", "web", "public", "docs");

await rm(destination, { recursive: true, force: true });
await mkdir(path.dirname(destination), { recursive: true });
await cp(source, destination, { recursive: true });

process.stdout.write(`Synced HTML documentation to ${destination}\n`);
