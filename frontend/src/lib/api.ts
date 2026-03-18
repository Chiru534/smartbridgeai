import axios from 'axios';
import { getToken, logout } from './auth';
import { toast } from 'sonner';

const api = axios.create({
    baseURL: 'http://localhost:8000',
});

// Request Interceptor: Attach Token
api.interceptors.request.use(
    (config) => {
        const token = getToken();
        if (token) {
            config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
    },
    (error) => {
        return Promise.reject(error);
    }
);

// Response Interceptor: Handle 401 & Global Errors
api.interceptors.response.use(
    (response) => {
        return response;
    },
    (error) => {
        if (error.response) {
            // Force logout and reload if token is invalid or expired
            if (error.response.status === 401 && window.location.pathname !== '/') {
                logout();
                toast.error('Session expired', {
                    description: 'Please log in again to continue.',
                });
                setTimeout(() => {
                    window.location.href = '/';
                }, 1500);
            } else if (error.response.status >= 500) {
                toast.error('Server Error', {
                    description: 'An unexpected error occurred on the server.',
                });
            }
        } else if (error.request) {
            // Network error
            toast.error('Network Error', {
                description: 'Could not connect to the server. Please check your internet connection.',
            });
        }
        return Promise.reject(error);
    }
);

export default api;
