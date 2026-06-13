import java.io.*;
import java.net.*;
import java.nio.*;
import java.nio.charset.*;
import java.util.*;
import java.time.*;
import java.time.format.*;

/**
 * ZKTeco MB10-VL - Direct TCP Fetcher
 * بروتوكول ZKTeco Binary مباشرة بدون SDK
 */
public class ZKFetcher {

    // ── إعدادات ─────────────────────────────────────────
    static final String IP      = "192.168.1.201"; // ← عدّل هذا
    static final int    PORT    = 4370;
    static final int    TIMEOUT = 10_000; // 10 ثانية

    // ── ثوابت البروتوكول ────────────────────────────────
    static final int CMD_CONNECT       = 1000;
    static final int CMD_EXIT          = 1001;
    static final int CMD_ENABLEDEVICE  = 1009;
    static final int CMD_DATA_WRRQ     = 1503; // طلب سجلات الحضور
    static final int CMD_DATA          = 1504;
    static final int CMD_FREE_DATA     = 1502;
    static final int CMD_GET_TIME      = 201;
    static final int CMD_USER_WRQ      = 1100; // طلب بيانات المستخدمين

    static final int CMD_ACK_OK        = 2000;
    static final int CMD_ACK_ERROR     = 2001;
    static final int CMD_ACK_DATA      = 2002;

    static final byte[] EMPTY = new byte[0];

    // ── حالة الاتصال ────────────────────────────────────
    static Socket      socket;
    static InputStream in;
    static OutputStream out;
    static int sessionId = 0;
    static int replyId   = 0;

    // ── مسار الإخراج ────────────────────────────────────
    static final String OUTPUT = "../input/attendance_raw.csv";

    // ════════════════════════════════════════════════════
    public static void main(String[] args) throws Exception {
        System.out.println("==============================================");
        System.out.println("  ZKTeco MB10-VL - Java TCP Fetcher");
        System.out.println("==============================================");

        String ip   = args.length > 0 ? args[0] : IP;
        int    port = args.length > 1 ? Integer.parseInt(args[1]) : PORT;

        // 1. اتصال
        System.out.printf("[...] Connecting to %s:%d%n", ip, port);
        socket = new Socket();
        socket.connect(new InetSocketAddress(ip, port), TIMEOUT);
        socket.setSoTimeout(TIMEOUT);
        in  = socket.getInputStream();
        out = socket.getOutputStream();
        System.out.println("[OK] TCP connected");

        // 2. Handshake
        connect();
        System.out.println("[OK] Handshake complete, session: " + sessionId);

        // 3. تفعيل الجهاز
        sendCommand(CMD_ENABLEDEVICE, new byte[]{1}, true);
        System.out.println("[OK] Device enabled");

        // 4. جلب أسماء الموظفين
        System.out.println("[...] Reading employee names...");
        Map<String, String> nameMap = readUsers();
        System.out.printf("[OK] %d employees found%n", nameMap.size());

        // 5. جلب سجلات الحضور
        System.out.println("[...] Reading attendance logs...");
        List<long[]> rawLogs = readAttendanceLogs();
        System.out.printf("[OK] %d raw punches fetched%n", rawLogs.size());

        // 6. قطع الاتصال
        sendCommand(CMD_EXIT, EMPTY, false);
        socket.close();
        System.out.println("[OK] Disconnected");

        // 7. معالجة وحفظ
        System.out.println("[...] Processing and saving...");
        List<String[]> daily = processDailyRecords(rawLogs, nameMap);
        saveCsv(daily);
        System.out.printf("[OK] Saved %d daily records%n", daily.size());
        System.out.printf("     File: %s%n", new File(OUTPUT).getCanonicalPath());
        System.out.println("[DONE]");
    }

    // ════════════════════════════════════════════════════
    // CONNECT HANDSHAKE
    // ════════════════════════════════════════════════════
    static void connect() throws Exception {
        // أرسل CMD_CONNECT مع session=0
        byte[] packet = buildPacket(CMD_CONNECT, EMPTY, 0, 0);
        out.write(packet);
        out.flush();

        byte[] resp = readPacket();
        int cmd = getShort(resp, 0);
        if (cmd != CMD_ACK_OK)
            throw new RuntimeException("Handshake failed, cmd=" + cmd);

        sessionId = getShort(resp, 4);
        replyId   = 0;
    }

    // ════════════════════════════════════════════════════
    // SEND COMMAND
    // ════════════════════════════════════════════════════
    static byte[] sendCommand(int cmd, byte[] data, boolean expectReply) throws Exception {
        replyId++;
        byte[] packet = buildPacket(cmd, data, sessionId, replyId);
        out.write(packet);
        out.flush();

        if (!expectReply) return EMPTY;

        byte[] resp = readPacket();
        int respCmd = getShort(resp, 0);
        if (respCmd != CMD_ACK_OK && respCmd != CMD_ACK_DATA && respCmd != CMD_DATA)
            throw new RuntimeException("Command " + cmd + " failed, response=" + respCmd);
        return resp;
    }

    // ════════════════════════════════════════════════════
    // READ USERS
    // ════════════════════════════════════════════════════
    static Map<String, String> readUsers() throws Exception {
        Map<String, String> map = new HashMap<>();
        try {
            // طلب بيانات المستخدمين
            byte[] reqData = "uid=0\t".getBytes(StandardCharsets.US_ASCII);
            byte[] resp = sendCommand(CMD_USER_WRQ, reqData, true);

            byte[] allData = readAllData(resp);
            if (allData == null || allData.length == 0) return map;

            // كل سجل مستخدم = 72 byte
            int recSize = 72;
            for (int i = 0; i + recSize <= allData.length; i += recSize) {
                String uid  = readString(allData, i, 5).trim();
                // privilege عند offset 5 (1 byte)
                String name = readString(allData, i + 8, 24).trim();
                if (!uid.isEmpty())
                    map.put(uid, name.isEmpty() ? "EMP_" + uid : name);
            }
        } catch (Exception e) {
            System.out.println("[WARN] Could not read users: " + e.getMessage());
        }
        return map;
    }

    // ════════════════════════════════════════════════════
    // READ ATTENDANCE LOGS
    // ════════════════════════════════════════════════════
    static List<long[]> readAttendanceLogs() throws Exception {
        List<long[]> logs = new ArrayList<>();

        // طلب جلب الـ logs
        byte[] reqData = "uid=0\t".getBytes(StandardCharsets.US_ASCII);
        byte[] resp = sendCommand(CMD_DATA_WRRQ, reqData, true);

        byte[] allData = readAllData(resp);
        if (allData == null || allData.length == 0) return logs;

        // كل سجل = 16 byte
        // [uid:2][reserved:2][timestamp:4][type:1][inout:1][reserved:6]
        int recSize = 16;
        for (int i = 0; i + recSize <= allData.length; i += recSize) {
            long uid       = getShortUnsigned(allData, i);
            long timestamp = getIntUnsigned(allData, i + 4);
            int  inOut     = allData[i + 9] & 0xFF;

            if (timestamp == 0) continue;

            // فك تشفير timestamp (ZKTeco encoding)
            long[] dt = decodeTimestamp(timestamp);
            if (dt == null) continue;

            logs.add(new long[]{ uid, dt[0], dt[1], dt[2], dt[3], dt[4], inOut });
        }
        return logs;
    }

    // ════════════════════════════════════════════════════
    // READ ALL DATA (multi-packet)
    // ════════════════════════════════════════════════════
    static byte[] readAllData(byte[] firstResp) throws Exception {
        ByteArrayOutputStream buf = new ByteArrayOutputStream();

        int respCmd = getShort(firstResp, 0);

        // إذا البيانات صغيرة جاءت في الرد المباشر
        if (respCmd == CMD_ACK_OK) {
            if (firstResp.length > 8)
                buf.write(firstResp, 8, firstResp.length - 8);
            return buf.toByteArray();
        }

        // بيانات كبيرة — تأتي على دفعات
        if (respCmd == CMD_ACK_DATA) {
            int totalSize = getInt(firstResp, 8);
            System.out.printf("     Data size: %d bytes%n", totalSize);

            // أرسل طلب استلام البيانات
            replyId++;
            byte[] req = buildPacket(CMD_DATA, EMPTY, sessionId, replyId);
            out.write(req);
            out.flush();

            int received = 0;
            while (received < totalSize) {
                try {
                    byte[] chunk = readPacket();
                    int chunkCmd = getShort(chunk, 0);
                    if (chunkCmd == CMD_DATA && chunk.length > 8) {
                        buf.write(chunk, 8, chunk.length - 8);
                        received += chunk.length - 8;
                    } else {
                        break;
                    }
                } catch (SocketTimeoutException e) {
                    break;
                }
            }
            return buf.toByteArray();
        }

        return buf.toByteArray();
    }

    // ════════════════════════════════════════════════════
    // DECODE ZKTECO TIMESTAMP
    // ZKTeco encodes time as: seconds since 2000-01-01
    // أو كـ packed integer
    // ════════════════════════════════════════════════════
    static long[] decodeTimestamp(long ts) {
        try {
            // ZKTeco timestamp = packed: second + minute*60 + hour*3600 + day*86400 + month*2678400 + (year-2000)*32140800
            long second = ts % 60;         ts /= 60;
            long minute = ts % 60;         ts /= 60;
            long hour   = ts % 24;         ts /= 24;
            long day    = ts % 31 + 1;     ts /= 31;
            long month  = ts % 12 + 1;     ts /= 12;
            long year   = ts + 2000;

            if (year < 2000 || year > 2099) return null;
            if (month < 1 || month > 12)    return null;
            if (day   < 1 || day   > 31)    return null;

            return new long[]{ year, month, day, hour, minute };
        } catch (Exception e) {
            return null;
        }
    }

    // ════════════════════════════════════════════════════
    // PROCESS DAILY RECORDS
    // ════════════════════════════════════════════════════
    static List<String[]> processDailyRecords(List<long[]> logs, Map<String, String> nameMap) {
        // تجميع حسب (uid + date)
        Map<String, List<long[]>> grouped = new TreeMap<>();
        for (long[] log : logs) {
            String uid  = String.valueOf(log[0]);
            String date = String.format("%04d-%02d-%02d", log[1], log[2], log[3]);
            String key  = uid + "|||" + date;
            grouped.computeIfAbsent(key, k -> new ArrayList<>()).add(log);
        }

        List<String[]> result = new ArrayList<>();
        for (Map.Entry<String, List<long[]>> entry : grouped.entrySet()) {
            String[] parts = entry.getKey().split("\\|\\|\\|");
            String uid  = parts[0];
            String date = parts[1];
            String name = nameMap.getOrDefault(uid, "EMP_" + uid);

            List<long[]> dayLogs = entry.getValue();
            dayLogs.sort(Comparator.comparingLong(a -> a[3] * 3600 + a[4] * 60 + a[5]));

            String inTime  = "";
            String outTime = "";

            if (dayLogs.size() == 1) {
                long[] l = dayLogs.get(0);
                String t = String.format("%02d:%02d:00", l[3], l[4]);
                if (l[3] < 12) inTime  = t;
                else           outTime = t;
            } else {
                long[] first = dayLogs.get(0);
                long[] last  = dayLogs.get(dayLogs.size() - 1);
                inTime  = String.format("%02d:%02d:00", first[3], first[4]);
                outTime = String.format("%02d:%02d:00", last[3],  last[4]);
            }

            // تنسيق التاريخ M/d/yyyy
            String[] dp   = date.split("-");
            String fmtDate = Integer.parseInt(dp[1]) + "/" + Integer.parseInt(dp[2]) + "/" + dp[0];

            result.add(new String[]{ name, fmtDate, inTime, outTime });
        }

        result.sort(Comparator.comparing((String[] a) -> a[0]).thenComparing(a -> a[1]));
        return result;
    }

    // ════════════════════════════════════════════════════
    // SAVE CSV
    // ════════════════════════════════════════════════════
    static void saveCsv(List<String[]> records) throws Exception {
        File f = new File(OUTPUT);
        f.getParentFile().mkdirs();
        try (PrintWriter w = new PrintWriter(new OutputStreamWriter(new FileOutputStream(f), StandardCharsets.UTF_8))) {
            // BOM لدعم Excel
            w.print('\uFEFF');
            w.println("Name,Date,Check In,Check Out");
            for (String[] r : records)
                w.printf("%s,%s,%s,%s%n", r[0], r[1], r[2], r[3]);
        }
    }

    // ════════════════════════════════════════════════════
    // PROTOCOL HELPERS
    // ════════════════════════════════════════════════════
    static byte[] buildPacket(int cmd, byte[] data, int sessionId, int replyId) {
        // Header = 8 bytes: [start:2][cmd:2][checksum:2][sessionId:2][replyId:2]
        // ZKTeco packet: start=0x5050
        int    total  = 8 + data.length;
        byte[] packet = new byte[total];
        packet[0] = (byte) 0x50;
        packet[1] = (byte) 0x50;
        putShort(packet, 2, cmd);
        putShort(packet, 4, 0); // checksum placeholder
        putShort(packet, 6, sessionId);
        // replyId في بعض الإصدارات offset 8 — نضعه في data[0:2]
        if (data.length >= 2) {
            System.arraycopy(data, 0, packet, 8, data.length);
        }
        int cs = checksum(packet);
        putShort(packet, 4, cs);
        return packet;
    }

    static int checksum(byte[] data) {
        long cs = 0;
        for (int i = 0; i < data.length; i += 2) {
            int word = (data[i] & 0xFF);
            if (i + 1 < data.length) word |= (data[i+1] & 0xFF) << 8;
            cs += word;
        }
        while (cs >> 16 != 0) cs = (cs & 0xFFFF) + (cs >> 16);
        return (int)(~cs & 0xFFFF);
    }

    static byte[] readPacket() throws Exception {
        // قراءة header أولاً (8 bytes)
        byte[] header = readExact(8);
        if (header[0] != (byte)0x50 || header[1] != (byte)0x50)
            throw new IOException("Invalid packet header");

        // بقية البيانات تأتي حتى timeout أو حسب size معروف
        ByteArrayOutputStream buf = new ByteArrayOutputStream();
        buf.write(header);

        byte[] extra = readAvailable();
        if (extra.length > 0) buf.write(extra);

        return buf.toByteArray();
    }

    static byte[] readExact(int n) throws Exception {
        byte[] buf = new byte[n];
        int    got = 0;
        while (got < n) {
            int r = in.read(buf, got, n - got);
            if (r < 0) throw new EOFException();
            got += r;
        }
        return buf;
    }

    static byte[] readAvailable() throws Exception {
        ByteArrayOutputStream buf = new ByteArrayOutputStream();
        byte[] tmp = new byte[4096];
        try {
            while (true) {
                int r = in.read(tmp);
                if (r < 0) break;
                buf.write(tmp, 0, r);
                if (in.available() == 0) break;
            }
        } catch (SocketTimeoutException e) { /* finished */ }
        return buf.toByteArray();
    }

    // ── byte helpers ────────────────────────────────────
    static void putShort(byte[] buf, int off, int val) {
        buf[off]   = (byte)(val & 0xFF);
        buf[off+1] = (byte)((val >> 8) & 0xFF);
    }

    static int getShort(byte[] buf, int off) {
        return (buf[off] & 0xFF) | ((buf[off+1] & 0xFF) << 8);
    }

    static long getShortUnsigned(byte[] buf, int off) {
        return getShort(buf, off) & 0xFFFFL;
    }

    static int getInt(byte[] buf, int off) {
        return (buf[off] & 0xFF) | ((buf[off+1] & 0xFF) << 8)
             | ((buf[off+2] & 0xFF) << 16) | ((buf[off+3] & 0xFF) << 24);
    }

    static long getIntUnsigned(byte[] buf, int off) {
        return getInt(buf, off) & 0xFFFFFFFFL;
    }

    static String readString(byte[] buf, int off, int len) {
        int end = off;
        while (end < off + len && end < buf.length && buf[end] != 0) end++;
        return new String(buf, off, end - off, StandardCharsets.UTF_8);
    }
}
