import React from 'react';
import { BrowserRouter as Router, Route, Switch } from 'react-router-dom';
import UploadForm from './components/UploadForm';
import ResultGallery from './components/ResultGallery';

const App: React.FC = () => {
  return (
    <Router>
      <div>
        <h1>Virtual Try-On Demo</h1>
        <Switch>
          <Route path="/" exact component={UploadForm} />
          <Route path="/results" component={ResultGallery} />
        </Switch>
      </div>
    </Router>
  );
};

export default App;