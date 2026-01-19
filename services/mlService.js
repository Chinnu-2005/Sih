const redis = require('redis');

class MLService {
  constructor() {
    let redisUrl = process.env.REDIS_URL || 'redis://localhost:6379';
    
    // Auto-fix Upstash URLs to use secure protocol
    if (redisUrl.includes('upstash.io') && redisUrl.startsWith('redis://')) {
      console.log('🔒 Upgrading Upstash URL to rediss://');
      redisUrl = redisUrl.replace('redis://', 'rediss://');
    }
    
    const isSecure = redisUrl.startsWith('rediss://');

    this.redisClient = redis.createClient({
      url: redisUrl,
      socket: {
        tls: isSecure, // Only enable TLS if protocol is rediss://
        rejectUnauthorized: false
      }
    });
    
    this.redisClient.on('error', (err) => {
      console.error('Redis Client Error:', err);
    });
    
    this.redisClient.on('connect', () => {
      console.log('ML Service connected to Redis');
    });
  }

  async initialize() {
    try {
      await this.redisClient.connect();
    } catch (error) {
      console.error('Failed to connect ML Service to Redis:', error);
    }
  }

  async queueClassificationJob(reportData) {
    try {
      // Ensure connection is open before pushing
      if (!this.redisClient.isOpen) {
        console.log('Redis client not open, attempting to connect...');
        await this.redisClient.connect();
      }

      const job = {
        reportId: reportData._id.toString(),
        description: reportData.description || '',
        imageUrl: reportData.image_url || null,
        title: reportData.title || '',
        timestamp: new Date().toISOString()
      };

      await this.redisClient.lPush('ml_classification_queue', JSON.stringify(job));
      console.log(`ML classification job queued for report ${reportData._id}`);
      
      return { success: true, jobId: reportData._id };
    } catch (error) {
      console.error('Error queueing ML classification job:', error);
      return { success: false, error: error.message };
    }
  }

  async getQueueStatus() {
    try {
      const queueLength = await this.redisClient.lLen('ml_classification_queue');
      return { queueLength };
    } catch (error) {
      console.error('Error getting queue status:', error);
      return { queueLength: 0 };
    }
  }
}

module.exports = new MLService();