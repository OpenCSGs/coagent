// npm install fetch-event-stream
import { events } from 'fetch-event-stream';
// npm install yargs
import yargs from 'yargs';
import { hideBin } from 'yargs/helpers';

class Channel {
  constructor(baseUrl, auth = '') {
    this.baseUrl = baseUrl;

    this.headers = {
      'Content-Type': 'application/json',
    };
    if (auth) {
      this.headers.Authorization = `Bearer ${auth}`;
    }
  }

  publish = async (addr, msg) => {
    const resp = await fetch(`${this.baseUrl}/runtime/channel/publish`, {
      method: 'POST',
      headers: this.headers,
      body: JSON.stringify({
        addr: addr,
        msg: msg,
      })
    });
    if (!resp.ok) {
      throw new Error(`HTTP error: ${resp.status}`);
    }
  }

  publishMulti = async (addr, msg) => {
  }

  subscribe = async (path, data, handler) => {
    const url = `${this.baseUrl}${path}`;
    let controller = new AbortController();

    let resp = await fetch(url, {
      signal: controller.signal,
      method: 'POST',
      headers: this.headers,
      body: JSON.stringify(data)
    });

    if (resp.ok) {
      let stream = events(resp, controller.signal);
      for await (let event of stream) {
        const data = JSON.parse(event.data);
        await handler(data);
      }
    }
  }
}

class Runtime {
  constructor(baseUrl, auth = '') {
    this.channel = new Channel(baseUrl, auth);
    this.factories = {};
    this.promises = {};
  }

  register = async (name, constructor, description = '') => {
    if (this.factories[name]) {
      throw new Error(`Agent with name ${name} already registered`);
    }
    this.factories[name] = constructor;

    this.channel.subscribe(
      '/runtime/register',
      {
        name: name,
        description: description
      },
      this.handle,
    );
  }

  handle = async (data) => {
    switch (data.header.type) {
      case 'AgentCreated':
        this.createAgent(data);
        break;

      case 'AgentDeleted':
        this.deleteAgent(data);
        break;

      default:
        console.log(`Unknown message type: ${data.header.type}`);
    }
  }

  createAgent = async (data) => {
    const content = JSON.parse(data.content);
    const addr = content.addr;

    console.log(`Creating agent with addr: ${JSON.stringify(addr)}`)

    let constructor = this.factories[addr.name];
    const agent = new constructor(this.channel, addr);
    this.promises[addr.name] = this.channel.subscribe(
      '/runtime/channel/subscribe',
      {addr: addr},
      agent.receive,
    );
  }

  deleteAgent = async (data) => {
  }
}

class Agent {
  constructor(channel, addr) {
    this.channel = channel;
    this.addr = addr;
  }

  receive = async (msg) => {
    console.log(`Received a message: ${JSON.stringify(msg)}`);

    let result = this.handle(msg);

    if (!msg.reply) {
      return
    }

    if (isAsyncIterator(result)) {
      for await (let r of result) {
        console.log(`partial result: ${JSON.stringify(r)}`);
        await this.channel.publish(msg.reply, r);
      }
      // End of the iteration, send an extra StopIteration message.
      const stop = {header: {type: 'StopIteration'}}
      await this.channel.publish(msg.reply, stop);
    } else {
      result = await result;
      console.log(`result: ${JSON.stringify(result)}`);
      await this.channel.publish(msg.reply, result);
    }
  }
}

function isAsyncIterator(obj) {
  return obj && typeof obj === 'object' && Symbol.asyncIterator in obj;
}

class Server extends Agent {
  handle = async (msg) => {
    if (msg.header.type === 'Ping') {
      return {header: {type: 'Pong'}};
    }
  }
}

class StreamServer extends Agent {
  async * handle(msg) {
    if (msg.header.type === 'Ping') {
      const words = ['Hi ', 'there, ', 'this ', 'is ', 'the ', 'Pong ', 'server.'];
      for (const word of words) {
        await new Promise(resolve => setTimeout(resolve, 600)); // sleep 0.6s
        yield {
          header: {type: 'PartialPong'},
          content: JSON.stringify({"content": word}),
        };
      }
    }
  }
}

const argv = yargs(hideBin(process.argv))
  .option('server', {
    type: 'string',
    description: 'The base URL.',
    default: 'http://127.0.0.1:8000',
  })
  .option('auth', {
    type: 'string',
    description: 'Authorization token.',
    default: '',
  })
  .parse();

const runtime = new Runtime(argv.server, argv.auth);
Promise.all([
  runtime.register('server', Server, 'The Pong Server.'),
  runtime.register('stream_server', StreamServer, 'The Stream Pong Server.'),
]).catch(console.error)
