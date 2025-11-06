#!/usr/bin/env node
const zmq = require('zeromq')
const { encode, decode } = require('@msgpack/msgpack')

function randInt(max) { return Math.floor(Math.random() * max) }
function randChoice(arr) { return arr[randInt(arr.length)] }
function sleep(ms) { return new Promise(r => setTimeout(r, ms)) }
function randomText(len = 20) {
  const chars = 'abcdefghijklmnopqrstuvwxyz0123456789'
  let s = ''
  for (let i = 0; i < len; i++) s += chars.charAt(randInt(chars.length))
  return s
}

async function main() {
  const req = new zmq.Request()
  await req.connect('tcp://broker:5555')
  console.log('Bot connected to broker:5555')

  // logical clock
  let clock = 0
  function incClock() { clock += 1; return clock }
  function updateClockFromReply(replyData) {
    try {
      if (replyData && typeof replyData.clock === 'number') {
        clock = Math.max(clock, replyData.clock)
      }
    } catch (e) {}
  }

  // pick a random username
  const username = 'bot-' + Math.random().toString(36).substring(2, 8)
  console.log('Bot username:', username)

  // send login
  const now = () => new Date().toLocaleTimeString('pt-BR')
  let data = { user: username, timestamp: now(), clock: incClock() }
  let reqMsg = { service: 'login', data }
  await req.send(encode(reqMsg))
  let [rawReply] = await req.receive()
  try { var reply = decode(rawReply) } catch (e) { reply = null }
  updateClockFromReply(reply && reply.data)
  console.log('login reply:', reply)

  while (true) {
    // 1. get channels
    reqMsg = { service: 'channels', data: { timestamp: now(), clock: incClock() } }
    await req.send(encode(reqMsg))
    [rawReply] = await req.receive()
    try { reply = decode(rawReply) } catch (e) { reply = null }
    updateClockFromReply(reply && reply.data)
    let channels = (reply && reply.data && reply.data.channels) || []
    if (!channels || channels.length === 0) {
      // create a channel
      const newChannel = 'chan-' + randomText(5)
      console.log('No channels, creating', newChannel)
      reqMsg = { service: 'channel', data: { channel: newChannel, timestamp: now(), clock: incClock() } }
      await req.send(encode(reqMsg))
      [rawReply] = await req.receive()
      try { reply = decode(rawReply) } catch (e) { reply = null }
      updateClockFromReply(reply && reply.data)
      channels = [newChannel]
    }

    // choose random channel
    const channel = randChoice(channels)
    console.log(`Chosen channel: ${channel}, will send 10 messages`)

    // send 10 messages
    for (let i = 0; i < 10; i++) {
      const message = `[${username}] ${randomText(40)}`
      const payload = { service: 'publish', data: { user: username, channel, message, timestamp: now(), clock: incClock() } }
      try {
        await req.send(encode(payload))
        [rawReply] = await req.receive()
        try { reply = decode(rawReply) } catch (e) { reply = null }
        updateClockFromReply(reply && reply.data)
        console.log('published ->', channel, reply && reply.data && reply.data.status)
      } catch (e) {
        console.warn('publish error', e && e.message)
      }
      // small delay
      await sleep(300 + randInt(700))
    }

    // loop back
    await sleep(500 + randInt(1000))
  }
}

main().catch(e => { console.error('bot error', e); process.exit(1) })
