def test_run_single_model():
    """Test running a single model"""
    settings = {
        'model_name': 'test_model',
        'projection_period': 10
    }
    test_df = pd.DataFrame({'test': [1, 2, 3]})
    model_points_list = {
        'test_product': test_df
    }
    assumptions = {'test': 'assumptions'}
    
    with patch('app.initialize_model') as mock_init_model:
        # Setup mock model
        mock_model = MagicMock()
        mock_pv_df = pd.DataFrame({'pv': [100, 200, 300]})
        mock_model.Results.pv_results.return_value = mock_pv_df
        mock_model.Results.analytics.return_value = pd.DataFrame({'metric': ['test']})
        mock_init_model.return_value = mock_model
        
        results = run_single_model('test_product', settings, model_points_list, assumptions)
        
        assert 'present_value' in results
        assert 'analytics' in results
        assert 'model_points_count' in results
        assert 'results_count' in results
        assert results['model_points_count'] == len(test_df)
        assert results['results_count'] == len(mock_pv_df)
        assert isinstance(results['present_value'], pd.DataFrame)
        assert isinstance(results['analytics'], pd.DataFrame)
        mock_init_model.assert_called_once()

def test_process_model_results():
    """Test processing model results"""
    settings = {
        'output_s3_url': 's3://test-bucket/output/'
    }
    model_results = {
        'present_value': pd.DataFrame({'pv': [100]}),
        'analytics': pd.DataFrame({'metric': ['test']})
    }
    start_time = datetime.datetime.now()
    
    with patch('app.upload_to_s3') as mock_upload:
        processed = process_model_results('test_product', model_results, settings, start_time)
        
        assert 'output_path' in processed
        assert 'results' in processed
        assert processed['results'] == model_results
        mock_upload.assert_called_once()

def test_process_single_product():
    """Test the full product processing flow"""
    settings = {
        'output_s3_url': 's3://test-bucket/output/',
        'model_name': 'test_model'
    }
    model_points_list = {
        'test_product': pd.DataFrame({'test': [1, 2, 3]})
    }
    assumptions = {'test': 'assumptions'}
    
    with patch('app.run_single_model') as mock_run_model, \
         patch('app.process_model_results') as mock_process_results, \
         patch('streamlit.empty') as mock_empty, \
         patch('streamlit.progress') as mock_progress:
        
        # Setup mock returns
        mock_run_model.return_value = {
            'present_value': pd.DataFrame(),
            'analytics': pd.DataFrame()
        }
        mock_process_results.return_value = {
            'output_path': 'test_path',
            'results': {'test': 'results'}
        }
        
        result, step = process_single_product(
            product='test_product',
            product_idx=1,
            settings=settings,
            model_points_list=model_points_list,
            assumptions=assumptions,
            total_products=1,
            progress_bar=mock_progress(),
            current_step=0,
            total_steps=2,
            start_time=datetime.datetime.now()
        )
        
        assert result == mock_process_results.return_value
        mock_run_model.assert_called_once()
        mock_process_results.assert_called_once()

def test_display_results():
    """Test displaying results with count comparison"""
    results = {
        'product1': {
            'present_value': pd.DataFrame({'value': [100]}),
            'analytics': pd.DataFrame({'metric': ['test']}),
            'model_points_count': 1,
            'results_count': 1
        },
        'product2': {
            'present_value': pd.DataFrame({'value': [100, 200]}),
            'analytics': pd.DataFrame({'metric': ['test']}),
            'model_points_count': 2,
            'results_count': 1  # Mismatch to test warning
        }
    }
    output_locations = ['s3://test-bucket/output/results_product1.xlsx']
    
    with patch('streamlit.success') as mock_success, \
         patch('streamlit.write') as mock_write, \
         patch('streamlit.subheader') as mock_subheader, \
         patch('streamlit.expander') as mock_expander, \
         patch('streamlit.columns') as mock_columns, \
         patch('streamlit.warning') as mock_warning:
        
        mock_expander.return_value.__enter__ = lambda x: None
        mock_expander.return_value.__exit__ = lambda x, y, z, w: None
        mock_columns.return_value = [MagicMock(), MagicMock()]
        
        display_results(results, output_locations, 10.5)
        
        mock_success.assert_called()
        mock_subheader.assert_called_once()
        mock_warning.assert_called_once()  # Should be called for product2's mismatch 