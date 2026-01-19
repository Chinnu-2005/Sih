const path=require('path');
require('dotenv').config({path:path.join(__dirname,'./.env')});

const express=require('express');
const http = require('http');
const socketIo = require('socket.io');

const connectDB=require('./db/db');
const app=require('./app');
const mlService = require('./services/mlService');
const aptosService = require('./services/aptosService');
const { getLocalIP } = require('./utils/networkUtils');
const PORT=process.env.PORT || 3000;

const server = http.createServer(app);
const io = socketIo(server, {
  cors: {
    origin: "*",
    methods: ["GET", "POST"]
  }
});

// Make io available globally
global.io = io;

connectDB();

// Initialize ML service
mlService.initialize().then(() => {
    console.log('ML Service initialized');
}).catch(err => {
    console.error('ML Service initialization failed:', err);
});

// Initialize Aptos service
aptosService.initialize().then(() => {
    console.log('✅ Aptos Blockchain Service initialized successfully');
    console.log('📍 Admin address:', aptosService.adminAccount?.address().hex());
    console.log('🔧 Service ready:', aptosService.initialized);
}).catch(err => {
    console.error('❌ Aptos Service initialization failed:', err);
});

// Initialize Monthly Reset Service
const monthlyResetService = require('./services/monthlyResetService');
monthlyResetService.scheduleMonthlyReset();
console.log('📅 Monthly reset service initialized');

server.listen(PORT, '0.0.0.0', ()=>{
    const localIP = getLocalIP();
    console.log(`Server is running on PORT : ${PORT}`);
    console.log(`🌐 Server accessible at:`);
    console.log(`   Local: http://localhost:${PORT}`);
    console.log(`   Network: http://${localIP}:${PORT}`);
    console.log('Socket.IO server initialized');
});

io.on('connection', (socket) => {
    console.log('User connected:', socket.id);
    
    socket.on('join-report', (reportId) => {
        socket.join(`report-${reportId}`);
        console.log(`User ${socket.id} joined report ${reportId}`);
    });
    
    socket.on('disconnect', () => {
        console.log('User disconnected:', socket.id);
    });
});

