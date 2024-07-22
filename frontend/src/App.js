import React, { useEffect } from 'react';
import { useSelector, useDispatch } from 'react-redux';
import { tempActions } from './features/temp/slice';
import { heatPlateActions } from './features/heatPlate/slice';
import { motorActions } from './features/motor/slice';

function App() {
  const dispatch = useDispatch();
  const temp_c = useSelector((state) => state.temp.temp.temp_c);
  const error = useSelector((state) => state.temp.error );

  const heatPlateState = useSelector((state) => state.heatPlate.state.data.relayState);
  const motorState = useSelector((state) => state.motor.state.data.relayState);

  useEffect(() => {
    const interval = setInterval(() => {
      dispatch(tempActions.fetchRequest());
    }, 1000);
    return () => clearInterval(interval);
  }, [dispatch]);

  useEffect(() => {
    const interval = setInterval(() => {
      dispatch(heatPlateActions.fetchState());
    }, 1000);
    return () => clearInterval(interval);
  }, [dispatch]);

  useEffect(() => {
    const interval = setInterval(() => {
      dispatch(motorActions.fetchState());
    }, 1000);
    return () => clearInterval(interval);
  }, [dispatch]);

  const dispatchHeatPlateCmd = (relayState) => () => {
    dispatch(heatPlateActions.sendCmd(relayState));
  };

  const dispatchMotorCmd = (relayState) => () => {
    dispatch(motorActions.sendCmd(relayState));
  };

  if (error) {
    return <div> Error: {error} </div>
  }

  return (
    <div>
      <p>Temperature: {temp_c} °C</p>
      <p>Heat Plate: {heatPlateState}</p>
      <button onClick={dispatchHeatPlateCmd('on')}>Turn on Heat Plate</button>
      <button onClick={dispatchHeatPlateCmd('off')}>Turn off Heat Plate</button>
      <p>Motor: {motorState}</p>
      <button onClick={dispatchMotorCmd('on')}>Turn on Motor</button>
      <button onClick={dispatchMotorCmd('off')}>Turn off Motor</button>
    </div>
  );
}

export default App;
