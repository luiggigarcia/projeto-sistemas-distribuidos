import org.zeromq.ZMQ;
import org.msgpack.core.MessagePack;
import org.msgpack.core.MessageUnpacker;
import org.msgpack.core.MessageFormat;
import org.msgpack.value.ValueType;
import java.io.IOException;
import java.util.Map;
import java.util.HashMap;
import org.msgpack.core.MessageBufferPacker;
import java.time.LocalTime;
import java.time.format.DateTimeFormatter;
import java.util.Scanner;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicLong;
import java.util.Set;
import java.util.concurrent.CopyOnWriteArraySet;
import org.zeromq.ZMQ.Poller;

public class Cliente {
    public static void main(String[] args) {
        ZMQ.Context reqContext = ZMQ.context(1);
        ZMQ.Socket socket = reqContext.socket(ZMQ.REQ);
        socket.connect("tcp://broker:5555");

    PubSubSubscriber subscriber = new PubSubSubscriber();
    subscriber.start();
        Scanner scanner = new Scanner(System.in);
    DateTimeFormatter formatter = DateTimeFormatter.ofPattern("HH:mm:ss");
    // logical clock
    AtomicLong clock = new AtomicLong(0);
    String opcao = "";
        while (!opcao.equals("0")) {
            System.out.println("\n=== MENU ===");
            System.out.println("1 - Login");
            System.out.println("2 - Listar usuários");
            System.out.println("3 - Criar canal");
            System.out.println("4 - Listar canais");
            System.out.println("5 - Publicar mensagem em canal");
            System.out.println("6 - Enviar mensagem direta para usuário");
            System.out.println("7 - Inscrever em canal");
            System.out.println("0 - Sair");
            System.out.print("Escolha uma opção: ");
            opcao = scanner.nextLine().trim();
            String user = null, channel = null, msg = null, dst = null;
            byte[] payload = null;
            String time_br = LocalTime.now().format(formatter);
            switch (opcao) {
                case "1":
                    System.out.print("Nome de usuário: ");
                    user = scanner.nextLine();
                    Map<String,Object> data1 = new HashMap<>();
                    data1.put("user", user);
                    data1.put("timestamp", time_br);
                    Map<String,Object> msg1 = new HashMap<>();
                    msg1.put("service", "login");
                    msg1.put("data", data1);
                
                    try {
                        MessageBufferPacker packer = MessagePack.newDefaultBufferPacker();
                        packer.packMapHeader(2);
                        packer.packString("service");
                        packer.packString("login");
                        packer.packString("data");
                        packer.packMapHeader(3);
                        packer.packString("user"); packer.packString(user == null ? "" : user);
                        packer.packString("timestamp"); packer.packString(time_br);
                        long cval = clock.incrementAndGet();
                        packer.packString("clock"); packer.packLong(cval);
                        packer.flush();
                        byte[] packed = packer.toByteArray();
                        packer.close();
                        payload = packed;
                    } catch (Exception e) {
                        String fallback = String.format("{\"service\":\"login\",\"data\":{\"user\":\"%s\",\"timestamp\":\"%s\"}}", user, time_br);
                        payload = fallback.getBytes(ZMQ.CHARSET);
                    }
                    break;
                case "2":
                    try {
                        MessageBufferPacker packer = MessagePack.newDefaultBufferPacker();
                        packer.packMapHeader(2);
                        packer.packString("service"); packer.packString("users");
                        packer.packString("data");
                        packer.packMapHeader(2);
                        packer.packString("timestamp"); packer.packString(time_br);
                        long cval2 = clock.incrementAndGet();
                        packer.packString("clock"); packer.packLong(cval2);
                        packer.flush();
                            byte[] packed = packer.toByteArray();
                            packer.close();
                            payload = packed;
                    } catch (Exception e) {
                        String fallback = String.format("{\"service\":\"users\",\"data\":{\"timestamp\":\"%s\"}}", time_br);
                            payload = fallback.getBytes(ZMQ.CHARSET);
                    }
                        break;
                case "3":
                    System.out.print("Nome do canal: ");
                    channel = scanner.nextLine();
                    try {
                        MessageBufferPacker packer = MessagePack.newDefaultBufferPacker();
                        packer.packMapHeader(2);
                        packer.packString("service"); packer.packString("channel");
                        packer.packString("data");
                        packer.packMapHeader(3);
                        packer.packString("channel"); packer.packString(channel == null ? "" : channel);
                        packer.packString("timestamp"); packer.packString(time_br);
                        long cval3 = clock.incrementAndGet();
                        packer.packString("clock"); packer.packLong(cval3);
                        packer.flush();
                        byte[] packed = packer.toByteArray();
                        packer.close();
                        payload = packed;
                    } catch (Exception e) {
                        String fallback = String.format("{\"service\":\"channel\",\"data\":{\"channel\":\"%s\",\"timestamp\":\"%s\"}}", channel, time_br);
                        payload = fallback.getBytes(ZMQ.CHARSET);
                    }
                    break;
                case "4":
                    try {
                        MessageBufferPacker packer = MessagePack.newDefaultBufferPacker();
                        packer.packMapHeader(2);
                        packer.packString("service"); packer.packString("channels");
                        packer.packString("data");
                        packer.packMapHeader(2);
                        packer.packString("timestamp"); packer.packString(time_br);
                        long cval4 = clock.incrementAndGet();
                        packer.packString("clock"); packer.packLong(cval4);
                        packer.flush();
                        byte[] packed = packer.toByteArray();
                        packer.close();
                        payload = packed;
                    } catch (Exception e) {
                        String fallback = String.format("{\"service\":\"channels\",\"data\":{\"timestamp\":\"%s\"}}", time_br);
                        payload = fallback.getBytes(ZMQ.CHARSET);
                    }
                    break;
                case "5":
                    System.out.print("Seu nome de usuário: ");
                    user = scanner.nextLine();
                    System.out.print("Nome do canal: ");
                    channel = scanner.nextLine();
                    System.out.print("Mensagem a ser publicada: ");
                    msg = scanner.nextLine();
                    try {
                        MessageBufferPacker packer = MessagePack.newDefaultBufferPacker();
                        packer.packMapHeader(2);
                        packer.packString("service"); packer.packString("publish");
                        packer.packString("data");
                        packer.packMapHeader(5);
                        packer.packString("user"); packer.packString(user == null ? "" : user);
                        packer.packString("channel"); packer.packString(channel == null ? "" : channel);
                        packer.packString("message"); packer.packString(msg == null ? "" : msg);
                        packer.packString("timestamp"); packer.packString(time_br);
                        long cval5 = clock.incrementAndGet();
                        packer.packString("clock"); packer.packLong(cval5);
                        packer.flush();
                        byte[] packed = packer.toByteArray();
                        packer.close();
                        payload = packed;
                    } catch (Exception e) {
                        String fallback = String.format("{\"service\":\"publish\",\"data\":{\"user\":\"%s\",\"channel\":\"%s\",\"message\":\"%s\",\"timestamp\":\"%s\"}}", user, channel, msg, time_br);
                        payload = fallback.getBytes(ZMQ.CHARSET);
                    }
                    break;
                case "7":
                    System.out.print("Nome do canal para inscrever: ");
                    String subChannel = scanner.nextLine();
                    if (subChannel != null && !subChannel.trim().isEmpty()) {
                        subscriber.subscribe(subChannel.trim());
                        System.out.println("Inscrito no canal: " + subChannel);
                    } else {
                        System.out.println("Canal inválido.");
                    }
                    continue;
                case "6":
                    System.out.print("Seu nome de usuário: ");
                    user = scanner.nextLine();
                    System.out.print("Nome do usuário de destino: ");
                    dst = scanner.nextLine();
                    System.out.print("Mensagem a ser enviada: ");
                    msg = scanner.nextLine();
                    try {
                        MessageBufferPacker packer = MessagePack.newDefaultBufferPacker();
                        packer.packMapHeader(2);
                        packer.packString("service"); packer.packString("message");
                        packer.packString("data");
                        packer.packMapHeader(5);
                        packer.packString("src"); packer.packString(user == null ? "" : user);
                        packer.packString("dst"); packer.packString(dst == null ? "" : dst);
                        packer.packString("message"); packer.packString(msg == null ? "" : msg);
                        packer.packString("timestamp"); packer.packString(time_br);
                        long cval7 = clock.incrementAndGet();
                        packer.packString("clock"); packer.packLong(cval7);
                        packer.flush();
                        byte[] packed = packer.toByteArray();
                        packer.close();
                        payload = packed;
                    } catch (Exception e) {
                        String fallback = String.format("{\"service\":\"message\",\"data\":{\"src\":\"%s\",\"dst\":\"%s\",\"message\":\"%s\",\"timestamp\":\"%s\"}}", user, dst, msg, time_br);
                        payload = fallback.getBytes(ZMQ.CHARSET);
                    }
                    break;
                case "0":
                    System.out.println("Saindo...");
                    try {
                        subscriber.close();
                    } catch (Exception e) {
                    }
                    continue;
                default:
                    System.out.println("Opção inválida! Tente novamente.");
                    continue;
            }
            if (payload != null) {
                socket.send(payload, 0);
                byte[] reply = socket.recv(0);
                Map<String,Object> replyMap = null;
                String replyStr = null;
                try {
                    replyMap = unpackMsgpack(reply);
                } catch (Exception e) {
                    replyMap = null;
                }
                if (replyMap != null) {
                    replyStr = mapToString(replyMap);
                    try {
                        Object dataObj = replyMap.get("data");
                        if (dataObj instanceof Map<?,?>) {
                            Object clk = ((Map<?,?>)dataObj).get("clock");
                            if (clk instanceof Number) {
                                long rclk = ((Number)clk).longValue();
                                long cur = clock.get();
                                if (rclk > cur) clock.set(rclk);
                            }
                        }
                    } catch (Exception e) {
                        // ignore
                    }
                } else {
                    replyStr = new String(reply, ZMQ.CHARSET);
                }
                System.out.println("Resposta do servidor: " + replyStr);
                if (opcao.equals("1") && user != null) {
                    boolean shouldSubscribe = false;
                    if (replyMap != null) {
                        Object dataObj = replyMap.get("data");
                        if (dataObj instanceof Map<?,?>) {
                            Object status = ((Map<?,?>)dataObj).get("status");
                            if ("sucesso".equals(status) || "logado".equals(status)) {
                                shouldSubscribe = true;
                            }
                        }
                    } else {
                        if (replyStr.contains("\"status\":\"sucesso\"") || replyStr.contains("\"status\":\"logado\"")) {
                            shouldSubscribe = true;
                        }
                    }
                    if (shouldSubscribe) {
                        subscriber.subscribe(user);
                        System.out.println("Inscrito automaticamente no tópico do usuário: " + user);
                    }
                }
            }
        }
        socket.close();
        reqContext.term();
        scanner.close();
    }

    static class PubSubSubscriber extends Thread {
        private ZMQ.Context ctx;
        private ZMQ.Socket sub;
        private AtomicBoolean running = new AtomicBoolean(true);
        private Set<String> topics = new CopyOnWriteArraySet<>();

        @Override
        public void run() {
            ctx = ZMQ.context(1);
            sub = ctx.socket(ZMQ.SUB);
            sub.connect("tcp://proxy_pubsub:5558");
            Poller poller = ctx.poller(1);
            poller.register(sub, Poller.POLLIN);

            while (running.get()) {
                try {
                    int rc = poller.poll(500);
                    if (rc > 0 && poller.pollin(0)) {
                        String msg = sub.recvStr(0);
                        if (msg != null) {
                            System.out.println("[RECEBIDO] " + msg);
                        }
                    }
                } catch (Exception e) {
                }
            }

            try {
                poller.close();
            } catch (Exception e) {}
            try { sub.close(); } catch (Exception e) {}
            try { ctx.term(); } catch (Exception e) {}
        }

        public void subscribe(String topic) {
            if (topic == null || topic.trim().isEmpty()) return;
            topics.add(topic);
            try {
                sub.subscribe(topic.getBytes(ZMQ.CHARSET));
            } catch (Exception e) {
            }
        }

        public void close() {
            running.set(false);
            try { this.interrupt(); } catch (Exception e) {}
        }
    }

    private static Map<String,Object> unpackMsgpack(byte[] bytes) throws IOException {
        MessageUnpacker unpacker = MessagePack.newDefaultUnpacker(bytes);
        Map<String,Object> result = new HashMap<>();
        int mapHeader = unpacker.unpackMapHeader();
        for (int i = 0; i < mapHeader; i++) {
            String key = unpacker.unpackString();
            MessageFormat mf = unpacker.getNextFormat();
            ValueType vt = mf.getValueType();
            if (vt == ValueType.MAP) {
                int innerSize = unpacker.unpackMapHeader();
                Map<String,Object> inner = new HashMap<>();
                for (int j = 0; j < innerSize; j++) {
                    String ik = unpacker.unpackString();
                    MessageFormat imf = unpacker.getNextFormat();
                    ValueType ivt = imf.getValueType();
                    if (ivt == ValueType.STRING) {
                        inner.put(ik, unpacker.unpackString());
                    } else if (ivt == ValueType.INTEGER) {
                        inner.put(ik, unpacker.unpackLong());
                    } else if (ivt == ValueType.BOOLEAN) {
                        inner.put(ik, unpacker.unpackBoolean());
                    } else {
                        inner.put(ik, unpacker.unpackValue().toString());
                    }
                }
                result.put(key, inner);
            } else if (vt == ValueType.STRING) {
                result.put(key, unpacker.unpackString());
            } else if (vt == ValueType.INTEGER) {
                result.put(key, unpacker.unpackLong());
            } else if (vt == ValueType.BOOLEAN) {
                result.put(key, unpacker.unpackBoolean());
            } else {
                result.put(key, unpacker.unpackValue().toString());
            }
        }
        return result;
    }

    private static String mapToString(Map<String,Object> map) {
        StringBuilder sb = new StringBuilder();
        sb.append("{");
        boolean first = true;
        for (Map.Entry<String,Object> e : map.entrySet()) {
            if (!first) sb.append(", ");
            first = false;
            sb.append('"').append(e.getKey()).append('"').append(": ");
            Object v = e.getValue();
            if (v instanceof Map) {
                sb.append(mapToString((Map<String,Object>)v));
            } else {
                sb.append('"').append(String.valueOf(v)).append('"');
            }
        }
        sb.append("}");
        return sb.toString();
    }
}
