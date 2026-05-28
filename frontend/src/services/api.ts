import axios from 'axios';

const API_BASE_URL = 'http://localhost:5000/api'; // Adjust the base URL as needed

export const uploadImage = async (formData) => {
    try {
        const response = await axios.post(`${API_BASE_URL}/upload`, formData, {
            headers: {
                'Content-Type': 'multipart/form-data',
            },
        });
        return response.data;
    } catch (error) {
        console.error('Error uploading image:', error);
        throw error;
    }
};

export const fetchGeneratedResults = async (userInput) => {
    try {
        const response = await axios.post(`${API_BASE_URL}/generate`, userInput);
        return response.data;
    } catch (error) {
        console.error('Error fetching generated results:', error);
        throw error;
    }
};