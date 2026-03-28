import axios from 'axios';
import { toast } from 'sonner';

const api = axios.create({
    baseURL: 'http://localhost:8000',
});

// Request Interceptor: no auth token needed in dev/test bypass mode
api.interceptors.request.use(
    (config) => config,
    (error) => Promise.reject(error)
);

// Response Interceptor: Handle Global Errors (401 redirect removed for test mode)
api.interceptors.response.use(
    (response) => response,
    (error) => {
        if (error.response?.status >= 500) {
            toast.error('Server Error', {
                description: 'An unexpected error occurred on the server.',
            });
        } else if (error.request) {
            toast.error('Network Error', {
                description: 'Could not connect to the server. Please check your connection.',
            });
        }
        return Promise.reject(error);
    }
);

export default api;
